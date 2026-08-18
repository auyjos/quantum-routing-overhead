"""Baseline joins, penalty ratios and summary statistics."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from routing_overhead.experiments import RESULT_COLUMNS, atomic_write, read_raw_results

BASELINE_TOPOLOGY = "complete_27"

# Strict composite key: a constrained run may only be divided by the complete-connectivity
# run of the same circuit instance, level, seed and basis.
JOIN_KEYS = (
    "circuit_family",
    "logical_qubits",
    "circuit_hash",
    "optimization_level",
    "transpiler_seed",
    "basis_gates",
)

PENALTIES = {
    "depth_penalty": "output_depth",
    "two_qubit_depth_penalty": "output_two_qubit_depth",
    "two_qubit_count_penalty": "output_two_qubit_count",
}

GROUP_KEYS = ("circuit_family", "logical_qubits", "topology", "optimization_level")

SUMMARY_METRICS = (
    "depth_penalty",
    "two_qubit_depth_penalty",
    "two_qubit_count_penalty",
    "compile_time_seconds",
    "output_depth",
    "output_two_qubit_depth",
    "output_two_qubit_count",
)


def add_penalties(frame: pd.DataFrame) -> pd.DataFrame:
    """Fill the three penalty columns from each row's complete-connectivity baseline."""
    merged = _with_baselines(frame)
    result = frame.reset_index(drop=True).copy()
    for penalty, column in PENALTIES.items():
        numerator = _floats(merged[column])
        denominator = _floats(merged[f"{column}__baseline"])
        usable = _mask((denominator > 0) & numerator.notna())
        ratio = np.full(len(result), np.nan)
        ratio[usable] = (numerator[usable] / denominator[usable]).to_numpy(dtype=float)
        result[penalty] = ratio
    return result


def penalty_warnings(frame: pd.DataFrame) -> list[str]:
    """Rows the plan says to investigate: missing baselines and zero denominators."""
    merged = _with_baselines(frame)
    warnings = []
    for penalty, column in PENALTIES.items():
        numerator = _floats(merged[column])
        denominator = _floats(merged[f"{column}__baseline"])
        positive = _mask(numerator > 0)
        for position in np.flatnonzero(positive & _mask(denominator.isna())):
            warnings.append(
                f"{_describe(merged.iloc[position])}: no complete baseline for {penalty}"
            )
        for position in np.flatnonzero(positive & _mask(denominator == 0)):
            warnings.append(f"{_describe(merged.iloc[position])}: zero baseline for {penalty}")
    return warnings


def geometric_mean(values) -> float:
    """Geometric mean, computed in log space; NaN unless every value is positive.

    The penalties this study reports are normalized ratios, and the geometric mean is
    the summary statistic that treats a 2x speed-up and a 2x slow-down symmetrically —
    the convention adopted for normalized compiler benchmarks. It is reported alongside
    the median rather than replacing it: the median stays robust to the exact-1.000
    spikes that structural embeddings produce, while the geometric mean is the figure
    comparable with other normalized benchmark results.

    A non-positive value makes the statistic undefined rather than zero, so it is
    reported as NaN instead of silently collapsing the whole group.
    """
    array = np.asarray(values, dtype=float)
    array = array[~np.isnan(array)]
    if array.size == 0 or np.any(array <= 0):
        return float("nan")
    return float(np.exp(np.mean(np.log(array))))


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    """Median/IQR-first summary across seeds for every configuration.

    `min` is also the best-of-seeds figure for every metric summarized here, since all
    of them — penalties, depths, counts, compile time — are lower-is-better. Qiskit's
    own guidance is to transpile repeatedly and keep the best output, so `min` is the
    number that describes the transpiler as it is actually used, while `median`
    describes the distribution a single unlucky run is drawn from.
    """
    metrics = [metric for metric in SUMMARY_METRICS if metric in frame.columns]
    records = []
    for keys, group in frame.groupby(list(GROUP_KEYS), dropna=False, sort=True):
        for metric in metrics:
            values = _floats(group[metric]).dropna().astype(float)
            if values.empty:
                continue
            records.append(
                {
                    **dict(zip(GROUP_KEYS, keys)),
                    "metric": metric,
                    "count": int(values.size),
                    "median": float(values.median()),
                    "q25": float(values.quantile(0.25)),
                    "q75": float(values.quantile(0.75)),
                    "iqr": float(values.quantile(0.75) - values.quantile(0.25)),
                    "min": float(values.min()),
                    "max": float(values.max()),
                    "mean": float(values.mean()),
                    "geometric_mean": geometric_mean(values.to_numpy()),
                    # Sample standard deviation is undefined at n=1; reporting 0.0 would
                    # present a configuration where every seed but one failed as having
                    # no variability at all.
                    "std": float(values.std(ddof=1)),
                }
            )
    return pd.DataFrame.from_records(
        records,
        columns=[
            *GROUP_KEYS,
            "metric",
            "count",
            "median",
            "q25",
            "q75",
            "iqr",
            "min",
            "max",
            "mean",
            "geometric_mean",
            "std",
        ],
    )


def pooled_summary(frame: pd.DataFrame, metric: str = "two_qubit_depth_penalty") -> pd.DataFrame:
    """Per-topology pooled statistics, single-run and best-of-seeds side by side.

    Two rows of evidence answer two different questions:

    * `median` / `geometric_mean` / IQR pool every individual compilation, and describe
      what one transpiler invocation with an arbitrary seed produces.
    * `best_of_seeds_*` first takes the minimum across the seeds of each configuration,
      then pools those minima. That is the documented way to use a stochastic router —
      compile several times, keep the best — so it is the figure that describes the
      overhead a practitioner would actually ship with.

    The gap between the two is the value of repeated transpilation, expressed in the
    same units as the headline penalty.
    """
    metric_values = _floats(frame[metric])
    working = frame.assign(**{metric: metric_values}).dropna(subset=[metric])
    per_configuration = (
        working.groupby(list(GROUP_KEYS), dropna=False, sort=True)[metric].min().reset_index()
    )
    records = []
    for topology, group in working.groupby("topology", dropna=False, sort=True):
        values = group[metric].astype(float)
        best = per_configuration.loc[
            per_configuration["topology"] == topology, metric
        ].astype(float)
        records.append(
            {
                "topology": topology,
                "metric": metric,
                "count": int(values.size),
                "median": float(values.median()),
                "q25": float(values.quantile(0.25)),
                "q75": float(values.quantile(0.75)),
                "geometric_mean": geometric_mean(values.to_numpy()),
                "min": float(values.min()),
                "max": float(values.max()),
                "configurations": int(best.size),
                "best_of_seeds_median": float(best.median()) if best.size else float("nan"),
                "best_of_seeds_geometric_mean": geometric_mean(best.to_numpy()),
            }
        )
    return pd.DataFrame.from_records(records)


def aggregate_run(run_dir) -> dict:
    """Fill penalties in the run's raw results and write the summary table."""
    run_dir = Path(run_dir)
    frame = add_penalties(read_raw_results(run_dir))[list(RESULT_COLUMNS)]
    summary = summarize(frame)
    # `raw_results.csv` doubles as the resume journal, so every replacement is atomic.
    atomic_write(run_dir / "raw_results.parquet", lambda path: frame.to_parquet(path, index=False))
    atomic_write(
        run_dir / "raw_results.csv", lambda path: frame.to_csv(path, index=False, na_rep="")
    )
    atomic_write(
        run_dir / "summary_results.parquet", lambda path: summary.to_parquet(path, index=False)
    )
    return {
        "rows": len(frame),
        "summary_rows": len(summary),
        "warnings": penalty_warnings(frame),
    }


def _with_baselines(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.reset_index(drop=True)
    baseline = frame[(frame["topology"] == BASELINE_TOPOLOGY) & frame["success"].astype(bool)]
    duplicated = baseline.duplicated(subset=list(JOIN_KEYS)).sum()
    if duplicated:
        raise ValueError(
            f"found {duplicated} duplicate {BASELINE_TOPOLOGY} baseline rows for the join key "
            f"{list(JOIN_KEYS)}"
        )
    baseline = baseline[[*JOIN_KEYS, *PENALTIES.values()]].rename(
        columns={column: f"{column}__baseline" for column in PENALTIES.values()}
    )
    return frame.merge(baseline, on=list(JOIN_KEYS), how="left", validate="many_to_one")


def _floats(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Float64")


def _mask(condition: pd.Series) -> np.ndarray:
    """Nullable comparisons yield pd.NA; treat a missing comparison as False."""
    return condition.fillna(False).to_numpy(dtype=bool)


def _describe(row: pd.Series) -> str:
    return (
        f"{row['circuit_family']} n={row['logical_qubits']} {row['topology']} "
        f"level={row['optimization_level']} seed={row['transpiler_seed']}"
    )
