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
from routing_overhead.topologies import (
    RELABELLED_BASES,
    base_topology,
    is_relabelled,
    is_sweep,
    sweep_index,
)

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


def available_sweeps(frame: pd.DataFrame) -> dict[str, int]:
    """Base topologies carrying a relabelling sweep, and how many members are present."""
    present = [name for name in frame["topology"].dropna().unique() if is_sweep(name)]
    counts: dict[str, int] = {}
    for name in present:
        base = base_topology(name)
        if base in set(frame["topology"].dropna().unique()):
            counts[base] = counts.get(base, 0) + 1
    return dict(sorted(counts.items()))


def sweep_distribution(
    frame: pd.DataFrame, metric: str = PRIMARY_METRIC, group=("optimization_level",)
) -> pd.DataFrame:
    """Where the study's own labelling falls among its relabellings.

    One row per (base topology, grouping). `identity_rank` counts how many sweep members
    came out *below* the identity labelling, so 0 means the study's maps produced the
    most favourable result of every labelling tested and `sweep_members` means the least.

    A single relabelling can only show that labelling matters somewhere. This shows
    whether the labelling actually used is typical, and how wide the effect is.
    """
    working = frame[frame["success"].astype(bool)] if "success" in frame else frame
    working = working.assign(**{metric: pd.to_numeric(working[metric], errors="coerce")})
    working = working.dropna(subset=[metric])
    working = working.assign(
        base=working["topology"].map(base_topology),
        is_sweep_member=working["topology"].map(is_sweep),
        is_control=working["topology"].map(is_relabelled),
    )
    keys = list(group)
    records = []
    for (base, *rest), block in working.groupby(["base", *keys], dropna=False, sort=True):
        sweep = block[block["is_sweep_member"]]
        if sweep.empty:
            continue
        medians = sweep.groupby("topology")[metric].median().sort_values()
        identity = block[~block["is_control"]][metric]
        named = block[block["is_control"] & ~block["is_sweep_member"]][metric]
        identity_median = float(identity.median()) if not identity.empty else float("nan")
        below = int((medians < identity_median).sum()) if not identity.empty else -1
        records.append(
            {
                "base_topology": base,
                **dict(zip(keys, rest)),
                "sweep_members": int(medians.size),
                "identity_median": identity_median,
                "named_control_median": (
                    float(named.median()) if not named.empty else float("nan")
                ),
                "sweep_min": float(medians.min()),
                "sweep_q25": float(medians.quantile(0.25)),
                "sweep_median": float(medians.median()),
                "sweep_q75": float(medians.quantile(0.75)),
                "sweep_max": float(medians.max()),
                "sweep_geometric_mean": geometric_mean(medians.to_numpy()),
                "spread_ratio": float(medians.max() / medians.min()),
                "identity_rank": below,
                "identity_percentile": (
                    100.0 * below / medians.size if below >= 0 else float("nan")
                ),
            }
        )
    return pd.DataFrame.from_records(records)


def ranking_robustness(
    frame: pd.DataFrame,
    left: str,
    right: str,
    metric: str = PRIMARY_METRIC,
    exclude_levels=(0,),
) -> pd.DataFrame:
    """How often each circuit family's topology ranking survives relabelling.

    For every sweep index the two base graphs are compared under the *same* permutation
    index, so the pair differs only in connectivity. A ranking that flips with the
    labelling is not a topology result.
    """
    working = frame[frame["success"].astype(bool)] if "success" in frame else frame
    working = working[~working["optimization_level"].isin(exclude_levels)]
    working = working.assign(**{metric: pd.to_numeric(working[metric], errors="coerce")})
    working = working.dropna(subset=[metric])
    working = working.assign(
        base=working["topology"].map(base_topology),
        index=working["topology"].map(sweep_index),
    )
    sweep = working[working["index"].notna()]
    records = []
    for family, block in sweep.groupby("circuit_family", dropna=False, sort=True):
        left_wins = right_wins = ties = 0
        lefts, rights = [], []
        for index in sorted(block["index"].dropna().unique()):
            cell = block[block["index"] == index]
            left_median = cell[cell["base"] == left][metric].median()
            right_median = cell[cell["base"] == right][metric].median()
            if pd.isna(left_median) or pd.isna(right_median):
                continue
            lefts.append(float(left_median))
            rights.append(float(right_median))
            # Ties are counted separately, never folded into a win for either side: a
            # family that embeds exactly on both graphs (penalty 1.000 everywhere) has
            # no ranking at all, and reporting it as a clean sweep for whichever side
            # the comparison happens to test second would invent a result.
            if left_median < right_median:
                left_wins += 1
            elif right_median < left_median:
                right_wins += 1
            else:
                ties += 1
        if not lefts:
            continue
        decided = left_wins + right_wins
        records.append(
            {
                "circuit_family": family,
                "comparisons": len(lefts),
                f"{left}_median_of_medians": float(np.median(lefts)),
                f"{right}_median_of_medians": float(np.median(rights)),
                f"{left}_cheaper": left_wins,
                f"{right}_cheaper": right_wins,
                "tied": ties,
                # Unanimity is only meaningful among comparisons that had a winner.
                "unanimous": decided > 0 and left_wins in (0, decided),
            }
        )
    return pd.DataFrame.from_records(records)


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
    # The named control only. Sweep members are also relabellings, but they belong to
    # the distribution analysis: pairing a base against 25 controls at once would make
    # this a many-to-one merge and silently average the sweep into the single-control
    # verdict.
    statistics["is_named_control"] = statistics["topology"].isin(RELABELLED_BASES)

    base = statistics[~statistics["is_control"]]
    control = statistics[statistics["is_named_control"]]
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
    sweeps = available_sweeps(frame)
    if not controls and not sweeps:
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

    distribution = pd.DataFrame()
    ranking = pd.DataFrame()
    if sweeps:
        distribution = sweep_distribution(frame, metric=metric)
        atomic_write(
            run_dir / "relabelling_distribution.csv",
            lambda path: distribution.to_csv(path, index=False),
        )
        bases = sorted(sweeps)
        if len(bases) == 2:
            ranking = ranking_robustness(frame, bases[1], bases[0], metric=metric)
            atomic_write(
                run_dir / "ranking_robustness.csv",
                lambda path: ranking.to_csv(path, index=False),
            )

    return {
        "controls": controls,
        "sweeps": sweeps,
        "distribution": distribution,
        "ranking": ranking,
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
    "available_sweeps",
    "classify",
    "control_run",
    "invariance_by_level",
    "label_invariance",
    "ranking_robustness",
    "sweep_distribution",
]
