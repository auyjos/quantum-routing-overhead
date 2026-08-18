"""Analysis of penalties.csv -> summary.json + sanity checks + printed tables."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import percentileofscore

ROOT = "/home/claude/work/artifacts/permsweep"

df = pd.read_csv(f"{ROOT}/penalties.csv")
raw = pd.read_csv(f"{ROOT}/raw.csv")
baseline = pd.read_csv(f"{ROOT}/baseline.csv")

RANDOM_LABELS = [f"r{i:02d}" for i in range(24)]
ALL_LABELS = ["identity", "stored"] + RANDOM_LABELS
BASES = ["line_27", "cairo_heavy_hex_27"]
LEVELS = [0, 1, 3]

summary: dict = {}

# ---------------------------------------------------------------------------
# 1. Sanity checks
# ---------------------------------------------------------------------------
sanity = {}
expected_raw_rows = 2 * 26 * 360
sanity["raw_row_count"] = {"actual": int(len(raw)), "expected": expected_raw_rows,
                            "ok": len(raw) == expected_raw_rows}
sanity["baseline_row_count"] = {"actual": int(len(baseline)), "expected": 360,
                                 "ok": len(baseline) == 360}
sanity["penalties_row_count"] = {"actual": int(len(df)), "expected": expected_raw_rows,
                                  "ok": len(df) == expected_raw_rows}

n_zero_denom = int((df["baseline_two_qubit_depth"] == 0).sum())
n_nan = int(df["two_qubit_depth_penalty"].isna().sum())
sanity["zero_denominators"] = {"count": n_zero_denom, "ok": n_zero_denom == 0}
sanity["nan_penalties"] = {"count": n_nan, "ok": n_nan == 0}


def pooled_median(sub: pd.DataFrame) -> float:
    return float(sub["two_qubit_depth_penalty"].median())


identity_line_all = pooled_median(df[(df.base_topology == "line_27") & (df.labeling_id == "identity")])
identity_line_excl0 = pooled_median(
    df[(df.base_topology == "line_27") & (df.labeling_id == "identity") & (df.optimization_level != 0)]
)
identity_cairo_all = pooled_median(
    df[(df.base_topology == "cairo_heavy_hex_27") & (df.labeling_id == "identity")]
)
identity_cairo_excl0 = pooled_median(
    df[(df.base_topology == "cairo_heavy_hex_27") & (df.labeling_id == "identity") & (df.optimization_level != 0)]
)

expected_checks = {
    "identity_line27_all_levels": (identity_line_all, 2.691),
    "identity_line27_excl_L0": (identity_line_excl0, 2.140),
    "identity_cairo_all_levels": (identity_cairo_all, 2.909),
    "identity_cairo_excl_L0": (identity_cairo_excl0, 2.304),
}
for name, (actual, expected) in expected_checks.items():
    deviation = abs(actual - expected)
    sanity[name] = {
        "actual": round(actual, 6),
        "expected": expected,
        "deviation": round(deviation, 6),
        "flag_gt_0.05": deviation > 0.05,
    }

summary["sanity_checks"] = sanity

# ---------------------------------------------------------------------------
# 2. Per (base_topology, labeling_id): pooled median (360 rows) and excl L0 (240 rows)
# ---------------------------------------------------------------------------
per_labeling = []
for base in BASES:
    for labeling in ALL_LABELS:
        sub = df[(df.base_topology == base) & (df.labeling_id == labeling)]
        sub_excl0 = sub[sub.optimization_level != 0]
        per_labeling.append(
            {
                "base_topology": base,
                "labeling_id": labeling,
                "n_all": int(len(sub)),
                "pooled_median_all_levels": pooled_median(sub),
                "n_excl_L0": int(len(sub_excl0)),
                "pooled_median_excl_L0": pooled_median(sub_excl0),
            }
        )
summary["per_labeling"] = per_labeling
per_labeling_df = pd.DataFrame(per_labeling)

# ---------------------------------------------------------------------------
# 3. Per (base_topology, level): distribution across 24 random labelings of pooled
#    median penalty; percentile rank of identity and stored within that distribution.
# ---------------------------------------------------------------------------
def distribution_stats(values: np.ndarray) -> dict:
    return {
        "min": float(np.min(values)),
        "q25": float(np.percentile(values, 25)),
        "median": float(np.median(values)),
        "q75": float(np.percentile(values, 75)),
        "max": float(np.max(values)),
    }


def percentile_rank(value: float, population: np.ndarray) -> float:
    # 'mean' kind: average of strict-less and less-or-equal percentile scores
    return float(percentileofscore(population, value, kind="mean"))


per_level = []
for base in BASES:
    for level in LEVELS:
        sub_level = df[(df.base_topology == base) & (df.optimization_level == level)]
        random_medians = []
        for labeling in RANDOM_LABELS:
            v = pooled_median(sub_level[sub_level.labeling_id == labeling])
            random_medians.append(v)
        random_medians = np.array(random_medians)
        identity_val = pooled_median(sub_level[sub_level.labeling_id == "identity"])
        stored_val = pooled_median(sub_level[sub_level.labeling_id == "stored"])
        stats = distribution_stats(random_medians)
        per_level.append(
            {
                "base_topology": base,
                "level": level,
                "n_random_labelings": len(random_medians),
                "random_distribution": stats,
                "identity_pooled_median": identity_val,
                "identity_percentile_rank_within_24_random": percentile_rank(identity_val, random_medians),
                "stored_pooled_median": stored_val,
                "stored_percentile_rank_within_24_random": percentile_rank(stored_val, random_medians),
            }
        )
summary["per_base_level_distribution"] = per_level

# ---------------------------------------------------------------------------
# 4. Specific cell percentile analyses
# ---------------------------------------------------------------------------
def cell_pooled_median(base: str, family: str | None, levels: list[int]) -> dict:
    """Pooled median penalty per labeling for a specific (family?, base, levels) cell."""
    mask = (df.base_topology == base) & (df.optimization_level.isin(levels))
    if family is not None:
        mask &= df.circuit_family == family
    sub = df[mask]
    random_medians = []
    for labeling in RANDOM_LABELS:
        random_medians.append(pooled_median(sub[sub.labeling_id == labeling]))
    random_medians = np.array(random_medians)
    identity_val = pooled_median(sub[sub.labeling_id == "identity"])
    stored_val = pooled_median(sub[sub.labeling_id == "stored"])
    stats = distribution_stats(random_medians)
    return {
        "base_topology": base,
        "circuit_family": family,
        "levels": levels,
        "n_rows_per_labeling": int(len(sub) / len(ALL_LABELS)),
        "random_distribution": stats,
        "identity_pooled_median": identity_val,
        "identity_percentile_rank_within_24_random": percentile_rank(identity_val, random_medians),
        "stored_pooled_median": stored_val,
        "stored_percentile_rank_within_24_random": percentile_rank(stored_val, random_medians),
    }


cells = [
    ("ghz_chain", "line_27", [0], "ghz_chain, line, L0 pooled sizes"),
    ("ghz_star", "line_27", [3], "ghz_star, line, L3 pooled sizes"),
    ("ghz_chain", "cairo_heavy_hex_27", [1, 3], "ghz_chain, cairo, L1+L3 pooled"),
    ("efficient_su2", "cairo_heavy_hex_27", [1, 3], "efficient_su2, cairo, L1+L3 pooled"),
]
cell_results = []
for family, base, levels, label in cells:
    result = cell_pooled_median(base, family, levels)
    result["label"] = label
    cell_results.append(result)
summary["specific_cells"] = cell_results

# ---------------------------------------------------------------------------
# 5. Per (base_topology, level): across-labeling spread ratio = max/min of 26 pooled medians
# ---------------------------------------------------------------------------
spread = []
for base in BASES:
    for level in LEVELS:
        sub_level = df[(df.base_topology == base) & (df.optimization_level == level)]
        medians = []
        for labeling in ALL_LABELS:
            medians.append(pooled_median(sub_level[sub_level.labeling_id == labeling]))
        medians = np.array(medians)
        spread.append(
            {
                "base_topology": base,
                "level": level,
                "n_labelings": len(medians),
                "min": float(np.min(medians)),
                "max": float(np.max(medians)),
                "spread_ratio_max_over_min": float(np.max(medians) / np.min(medians)),
            }
        )
summary["spread_ratio"] = spread

with open(f"{ROOT}/summary.json", "w") as f:
    json.dump(summary, f, indent=2)

# ---------------------------------------------------------------------------
# Print compact tables
# ---------------------------------------------------------------------------
print("=== SANITY CHECKS ===")
for k, v in sanity.items():
    print(k, v)

print("\n=== PER (base, labeling) POOLED MEDIANS (52 rows) ===")
print(per_labeling_df.to_string(index=False))

print("\n=== PER (base, level) RANDOM DISTRIBUTION + IDENTITY/STORED PERCENTILE ===")
for row in per_level:
    print(row)

print("\n=== SPECIFIC CELLS ===")
for row in cell_results:
    print(row)

print("\n=== SPREAD RATIO PER (base, level) ===")
for row in spread:
    print(row)
