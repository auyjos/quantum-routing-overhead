"""Label-permutation control: separating connectivity from physical-qubit labelling.

The main experiment fixes the circuit, the qubit count, the basis, the level and the
seed, and varies connectivity. One thing it does not hold fixed is the *labelling* of
the coupling graph, and Qiskit's initial-layout selection is sensitive to it:
`TrivialLayout` maps logical qubit i to physical qubit i, and the circuit builders index
the GHZ chain and the circular Efficient SU(2) entangler on `(i, i+1)` — precisely how
`CouplingMap.from_line(27)` numbers its nodes.

This module compares each constrained topology against a relabelled copy of the *same
graph* (see `topologies.RELABELLED_BASES`). Because every connectivity property is
identical by construction, any difference in the compiled result is attributable to
labelling alone:

* a level whose penalties are unchanged is **label-invariant**, and its cross-topology
  comparison is clean;
* a level whose penalties move is measuring index alignment as well as connectivity,
  and cannot carry a topology claim on its own.

Nothing here re-runs a compilation. It reads the journalled rows of a run whose grid
included both a base topology and its control.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from routing_overhead.aggregation import GROUP_KEYS, geometric_mean
from routing_overhead.experiments import atomic_write
from routing_overhead.topologies import RELABELLED_BASES, base_topology, is_relabelled

PRIMARY_METRIC = "two_qubit_depth_penalty"

# Below this, a base/control difference is reported as label-invariant. Penalties are
# ratios of small integers, so exactly-equal medians are the common case and this
# tolerance only absorbs floating-point noise in the division, not a real shift.
INVARIANCE_TOLERANCE = 1e-9

COMPARISON_KEYS = ("circuit_family", "logical_qubits", "optimization_level")

REPORT_COLUMNS = (
    "base_topology",
    *COMPARISON_KEYS,
    "seeds",
    "base_median",
    "relabelled_median",
    "base_min",
    "base_max",
    "relabelled_min",
    "relabelled_max",
    "absolute_shift",
    "relative_shift",
    "label_invariant",
    "seed_ranges_overlap",
    "systematic",
)


def available_controls(frame: pd.DataFrame) -> list[str]:
    """Base topologies for which this frame carries both the base and its control."""
    present = set(frame["topology"].dropna().unique())
    return sorted(
        base
        for control, base in RELABELLED_BASES.items()
        if control in present and base in present
    )


def label_invariance(frame: pd.DataFrame, metric: str = PRIMARY_METRIC) -> pd.DataFrame:
    """Per-configuration base-versus-control comparison of `metric`.

    One row per (base topology, circuit family, logical size, optimization level).
    `relative_shift` is the control median divided by the base median, so 1.0 means the
    relabelling changed nothing at all.

    Two verdict columns, because a median comparison alone cannot tell a real labelling
    effect from ordinary seed scatter:

    * `label_invariant` — the medians agree exactly.
    * `systematic` — the base and control seed ranges do not overlap at all, so *every*
      seed moved the same way. This is the strong claim: it cannot be produced by
      stochastic routing noise around a shared centre, only by the relabelling.
    """
    successes = frame[frame["success"].astype(bool)] if "success" in frame else frame
    working = successes.assign(**{metric: pd.to_numeric(successes[metric], errors="coerce")})
    working = working.dropna(subset=[metric])
    if working.empty:
        return pd.DataFrame(columns=list(REPORT_COLUMNS))

    statistics = (
        working.groupby(list(GROUP_KEYS), dropna=False, sort=True)[metric]
        .agg(["median", "min", "max", "size"])
        .reset_index()
    )
    statistics["base_topology"] = statistics["topology"].map(base_topology)
    statistics["is_control"] = statistics["topology"].map(is_relabelled)

    base = statistics[~statistics["is_control"]]
    control = statistics[statistics["is_control"]]
    merged = base.merge(
        control,
        on=["base_topology", *COMPARISON_KEYS],
        how="inner",
        suffixes=("_base", "_control"),
        validate="one_to_one",
    )
    if merged.empty:
        return pd.DataFrame(columns=list(REPORT_COLUMNS))

    base_median = merged["median_base"].astype(float)
    control_median = merged["median_control"].astype(float)
    base_min = merged["min_base"].astype(float)
    base_max = merged["max_base"].astype(float)
    control_min = merged["min_control"].astype(float)
    control_max = merged["max_control"].astype(float)
    shift = (control_median - base_median).abs()
    overlap = (base_min <= control_max) & (control_min <= base_max)
    report = pd.DataFrame(
        {
            "base_topology": merged["base_topology"],
            **{key: merged[key] for key in COMPARISON_KEYS},
            # Seed counts must agree for the comparison to be like-for-like; a mismatch
            # is surfaced rather than averaged away.
            "seeds": merged[["size_base", "size_control"]].min(axis=1).astype(int),
            "base_median": base_median,
            "relabelled_median": control_median,
            "base_min": base_min,
            "base_max": base_max,
            "relabelled_min": control_min,
            "relabelled_max": control_max,
            "absolute_shift": shift,
            "relative_shift": np.where(
                base_median > 0, control_median / base_median, np.nan
            ),
            "label_invariant": shift <= INVARIANCE_TOLERANCE,
            "seed_ranges_overlap": overlap,
            "systematic": ~overlap,
        }
    )
    return report.sort_values(
        ["base_topology", "optimization_level", "circuit_family", "logical_qubits"]
    ).reset_index(drop=True)[list(REPORT_COLUMNS)]


BY_LEVEL_COLUMNS = (
    "base_topology",
    "optimization_level",
    "configurations",
    "label_invariant",
    "invariant_fraction",
    "systematic",
    "systematic_fraction",
    "median_relative_shift",
    "geometric_mean_relative_shift",
    "max_relative_shift",
    "verdict",
)

# A level is only called clean if no configuration shifted systematically and the
# geometric mean of the shifts sits at 1. Ratios are compared in log space, so the same
# tolerance covers a shift in either direction.
GEOMETRIC_TOLERANCE = 0.02


def classify(group: pd.DataFrame) -> str:
    """Three-way verdict for one level of one base topology.

    * `label-invariant` — nothing moved at all.
    * `noise-only` — some configurations moved, but never beyond their seed scatter and
      not in a consistent direction, so the level carries no labelling bias.
    * `label-sensitive` — at least one configuration moved with base and control seed
      ranges disjoint, or the shifts are biased away from 1 overall.
    """
    if bool(group["label_invariant"].all()):
        return "label-invariant"
    biased = abs(np.log(geometric_mean(group["relative_shift"]))) > GEOMETRIC_TOLERANCE
    if bool(group["systematic"].any()) or biased:
        return "label-sensitive"
    return "noise-only"


def invariance_by_level(report: pd.DataFrame) -> pd.DataFrame:
    """Roll the per-configuration comparison up to one row per level and base topology."""
    if report.empty:
        return pd.DataFrame(columns=list(BY_LEVEL_COLUMNS))
    records = []
    for (base, level), group in report.groupby(
        ["base_topology", "optimization_level"], dropna=False, sort=True
    ):
        invariant = int(group["label_invariant"].sum())
        systematic = int(group["systematic"].sum())
        records.append(
            {
                "base_topology": base,
                "optimization_level": int(level),
                "configurations": len(group),
                "label_invariant": invariant,
                "invariant_fraction": invariant / len(group),
                "systematic": systematic,
                "systematic_fraction": systematic / len(group),
                "median_relative_shift": float(group["relative_shift"].median()),
                "geometric_mean_relative_shift": geometric_mean(group["relative_shift"]),
                "max_relative_shift": float(group["relative_shift"].max()),
                "verdict": classify(group),
            }
        )
    return pd.DataFrame.from_records(records)


def control_run(run_dir, metric: str = PRIMARY_METRIC) -> dict:
    """Write the label-invariance tables for a run and report what they show."""
    from routing_overhead.experiments import read_raw_results

    run_dir = Path(run_dir)
    frame = read_raw_results(run_dir)
    controls = available_controls(frame)
    if not controls:
        raise ValueError(
            "this run has no label-permutation control: its grid must include a "
            f"relabelled topology alongside its base, e.g. {min(RELABELLED_BASES)!r}"
        )
    report = label_invariance(frame, metric=metric)
    by_level = invariance_by_level(report)
    atomic_write(
        run_dir / "label_invariance.csv", lambda path: report.to_csv(path, index=False)
    )
    atomic_write(
        run_dir / "label_invariance_by_level.csv",
        lambda path: by_level.to_csv(path, index=False),
    )
    return {
        "controls": controls,
        "metric": metric,
        "configurations": len(report),
        "report": report,
        "by_level": by_level,
        "clean_levels": sorted(
            int(level)
            for level, group in by_level.groupby("optimization_level")
            if bool(group["verdict"].isin(("label-invariant", "noise-only")).all())
        ),
        "systematic": report[report["systematic"]],
    }


__all__ = [
    "available_controls",
    "classify",
    "control_run",
    "invariance_by_level",
    "label_invariance",
]
