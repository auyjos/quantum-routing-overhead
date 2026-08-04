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


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    """Median/IQR-first summary across seeds for every configuration."""
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
            "std",
        ],
    )


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
