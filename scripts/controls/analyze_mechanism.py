"""Attribution analysis: does VF2Layout's stop reason explain label (in)variance?"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

MECH_DIR = "/home/claude/work/artifacts/mechanism"
LI_PATH = "/home/claude/work/artifacts/runs/control-label-permutation/label_invariance.csv"

attribution = pd.read_csv(f"{MECH_DIR}/attribution.csv")
label_inv = pd.read_csv(LI_PATH)
label_inv = label_inv[label_inv["optimization_level"].isin([1, 3])].copy()

BASE_MAP = {
    "line_27": "line_27",
    "line_27_relabelled": "line_27",
    "cairo_heavy_hex_27": "cairo_heavy_hex_27",
    "cairo_heavy_hex_27_relabelled": "cairo_heavy_hex_27",
}
attribution["base_topology"] = attribution["topology"].map(BASE_MAP)

# ---------------------------------------------------------------------------
# Step 5a: per (base_topology, family, size, level) classification over the 10
# rows (5 seeds x base+relabelled).
# ---------------------------------------------------------------------------
def classify_group(g: pd.DataFrame) -> str:
    n = len(g)
    solved = (g["vf2_stop_reason"] == "SOLUTION_FOUND").sum()
    trivial = g["vf2_stop_reason"].isna().sum()  # VF2Layout skipped: trivial layout already valid
    failed = (g["vf2_stop_reason"] == "NO_SOLUTION_FOUND").sum()
    assert solved + trivial + failed == n, (solved, trivial, failed, n)
    if solved == n:
        return "vf2_solved"
    if failed == n:
        return "vf2_failed"
    if trivial == n:
        return "trivial_sufficient"
    return "mixed"


group_keys = ["base_topology", "circuit_family", "logical_qubits", "optimization_level"]
class_rows = []
for keys, g in attribution.groupby(group_keys, sort=True):
    d = dict(zip(group_keys, keys))
    d["n_rows"] = len(g)
    d["n_solution_found"] = int((g["vf2_stop_reason"] == "SOLUTION_FOUND").sum())
    d["n_no_solution_found"] = int((g["vf2_stop_reason"] == "NO_SOLUTION_FOUND").sum())
    d["n_trivial_sufficient"] = int(g["vf2_stop_reason"].isna().sum())
    d["classification"] = classify_group(g)
    # also record whether base vs relabelled disagree in classification (per-topology, not per-row)
    per_topo = g.groupby("topology")["vf2_stop_reason"].apply(
        lambda s: "SOLUTION_FOUND" if (s == "SOLUTION_FOUND").all()
        else ("NO_SOLUTION_FOUND" if (s == "NO_SOLUTION_FOUND").all()
              else ("TRIVIAL_SUFFICIENT" if s.isna().all() else "MIXED_SEEDS"))
    )
    d["per_topology_reason"] = json.dumps(per_topo.to_dict())
    class_rows.append(d)

classification = pd.DataFrame.from_records(class_rows)
classification.to_csv(f"{MECH_DIR}/classification.csv", index=False)

class_counts = classification["classification"].value_counts().to_dict()

# ---------------------------------------------------------------------------
# Step 5b: join with label_invariance.csv -> contingency tables
# ---------------------------------------------------------------------------
joined = classification.merge(
    label_inv,
    on=["base_topology", "circuit_family", "logical_qubits", "optimization_level"],
    how="inner",
    validate="one_to_one",
)
assert len(joined) == len(classification) == len(label_inv) == 96, (
    len(joined), len(classification), len(label_inv)
)

# contingency: vf2_solved vs label_invariant (restricted to the vf2_solved/vf2_failed rows,
# but report full table across all classes for completeness)
contingency_full = pd.crosstab(joined["classification"], joined["label_invariant"])
contingency_full.columns = [f"label_invariant={c}" for c in contingency_full.columns]

contingency_solved_vs_invariant = pd.crosstab(
    joined["classification"] == "vf2_solved", joined["label_invariant"]
)
contingency_solved_vs_invariant.index = [
    f"vf2_solved={i}" for i in contingency_solved_vs_invariant.index
]
contingency_solved_vs_invariant.columns = [
    f"label_invariant={c}" for c in contingency_solved_vs_invariant.columns
]

contingency_failed_vs_systematic = pd.crosstab(
    joined["classification"] == "vf2_failed", joined["systematic"]
)
contingency_failed_vs_systematic.index = [
    f"vf2_failed={i}" for i in contingency_failed_vs_systematic.index
]
contingency_failed_vs_systematic.columns = [
    f"systematic={c}" for c in contingency_failed_vs_systematic.columns
]

# Exceptions: vf2_solved but NOT label_invariant, or vf2_failed but NOT systematic,
# or vice versa (label_invariant but not vf2_solved / systematic but not vf2_failed)
exc_solved_not_invariant = joined[
    (joined["classification"] == "vf2_solved") & (~joined["label_invariant"])
]
exc_invariant_not_solved = joined[
    (joined["label_invariant"]) & (joined["classification"] != "vf2_solved")
]
exc_failed_not_systematic = joined[
    (joined["classification"] == "vf2_failed") & (~joined["systematic"])
]
exc_systematic_not_failed = joined[
    (joined["systematic"]) & (joined["classification"] != "vf2_failed")
]
mixed_rows = joined[joined["classification"] == "mixed"]
trivial_rows = joined[joined["classification"] == "trivial_sufficient"]

# ---------------------------------------------------------------------------
# Step 5c: configs where VF2 solved on base but failed on relabelled (or vice versa)
# ---------------------------------------------------------------------------
def per_topology_verdict(reason_series: pd.Series) -> str:
    if (reason_series == "SOLUTION_FOUND").all():
        return "SOLUTION_FOUND"
    if (reason_series == "NO_SOLUTION_FOUND").all():
        return "NO_SOLUTION_FOUND"
    if reason_series.isna().all():
        return "TRIVIAL_SUFFICIENT"
    return "MIXED_SEEDS"


topo_summary = (
    attribution.groupby(["base_topology", "circuit_family", "logical_qubits", "optimization_level", "topology"])[
        "vf2_stop_reason"
    ]
    .apply(per_topology_verdict)
    .reset_index()
    .rename(columns={"vf2_stop_reason": "verdict"})
)
topo_summary["is_relabelled"] = topo_summary["topology"].str.endswith("_relabelled")
pivot = topo_summary.pivot_table(
    index=["base_topology", "circuit_family", "logical_qubits", "optimization_level"],
    columns="is_relabelled",
    values="verdict",
    aggfunc="first",
).reset_index()
pivot.columns = [
    "base_topology", "circuit_family", "logical_qubits", "optimization_level",
    "base_verdict", "relabelled_verdict",
]
base_vs_relabelled_disagree = pivot[pivot["base_verdict"] != pivot["relabelled_verdict"]]

# ---------------------------------------------------------------------------
# Step 5d: verify prior claims
# ---------------------------------------------------------------------------
def penalty_ok(subframe, expected=1.0, tol=1e-9):
    return bool((np.isclose(subframe["penalty"], expected, atol=tol)).all())


claims = {}

# efficient_su2/cairo n=12,20 (L1,L3): SOLUTION_FOUND with penalty exactly 1.0
sub = attribution[
    (attribution["base_topology"] == "cairo_heavy_hex_27")
    & (attribution["circuit_family"] == "efficient_su2")
    & (attribution["logical_qubits"].isin([12, 20]))
    & (attribution["optimization_level"].isin([1, 3]))
]
claims["efficient_su2_cairo_n12_n20_L1_L3_solution_found_penalty_1"] = {
    "n_rows": len(sub),
    "all_solution_found": bool((sub["vf2_stop_reason"] == "SOLUTION_FOUND").all()),
    "all_penalty_1": penalty_ok(sub),
    "pass": bool((sub["vf2_stop_reason"] == "SOLUTION_FOUND").all() and penalty_ok(sub)),
    "detail": sub[
        ["topology", "logical_qubits", "optimization_level", "transpiler_seed", "vf2_stop_reason", "penalty"]
    ].to_dict(orient="records"),
}

# ghz_chain/line all sizes SOLUTION_FOUND penalty 1.0 (accepting trivial-sufficient
# as the mechanism where VF2Layout never ran because the trivial layout already worked)
sub = attribution[
    (attribution["base_topology"] == "line_27")
    & (attribution["circuit_family"] == "ghz_chain")
    & (attribution["optimization_level"].isin([1, 3]))
]
solved_or_trivial = sub["vf2_stop_reason"].isin(["SOLUTION_FOUND"]) | sub["vf2_stop_reason"].isna()
claims["ghz_chain_line_all_sizes_solution_found_penalty_1"] = {
    "n_rows": len(sub),
    "all_solution_found_strict": bool((sub["vf2_stop_reason"] == "SOLUTION_FOUND").all()),
    "all_solved_or_trivial_sufficient": bool(solved_or_trivial.all()),
    "n_trivial_sufficient": int(sub["vf2_stop_reason"].isna().sum()),
    "all_penalty_1": penalty_ok(sub),
    "pass": bool(solved_or_trivial.all() and penalty_ok(sub)),
    "note": (
        "Strict SOLUTION_FOUND claim FAILS for the level-1 identity-labelled ghz_chain "
        "rows: VF2Layout is skipped there because CheckMap already finds the trivial "
        "layout swap-mapped (property_set['is_swap_mapped']=True), so "
        "VF2Layout_stop_reason is never set (NaN), not SOLUTION_FOUND. Penalty is still "
        "exactly 1.0 in every row. All level-3 ghz_chain/line rows and level-1 "
        "ghz_chain/line_27_relabelled rows do show strict SOLUTION_FOUND."
    ),
    "trivial_sufficient_rows": sub[sub["vf2_stop_reason"].isna()][
        ["topology", "logical_qubits", "optimization_level", "transpiler_seed", "penalty"]
    ].to_dict(orient="records"),
}

# ghz_chain/cairo n=24 NOT solution-found
sub = attribution[
    (attribution["base_topology"] == "cairo_heavy_hex_27")
    & (attribution["circuit_family"] == "ghz_chain")
    & (attribution["logical_qubits"] == 24)
    & (attribution["optimization_level"].isin([1, 3]))
]
claims["ghz_chain_cairo_n24_not_solution_found"] = {
    "n_rows": len(sub),
    "any_solution_found": bool((sub["vf2_stop_reason"] == "SOLUTION_FOUND").any()),
    "all_no_solution_found": bool((sub["vf2_stop_reason"] == "NO_SOLUTION_FOUND").all()),
    "pass": bool(not (sub["vf2_stop_reason"] == "SOLUTION_FOUND").any()),
    "detail": sub[
        ["topology", "logical_qubits", "optimization_level", "transpiler_seed", "vf2_stop_reason", "penalty"]
    ].to_dict(orient="records"),
}

# ---------------------------------------------------------------------------
# Step 6: sanity check -- identity-labelled penalties match canonical figure
# ghz_star line L3 n=24 median approx 2.087
# ---------------------------------------------------------------------------
sub = attribution[
    (attribution["topology"] == "line_27")
    & (attribution["circuit_family"] == "ghz_star")
    & (attribution["logical_qubits"] == 24)
    & (attribution["optimization_level"] == 3)
]
median_val = float(sub["penalty"].median())
canonical = 2.087
deviation = abs(median_val - canonical)
sanity = {
    "ghz_star_line_L3_n24": {
        "n_rows": len(sub),
        "median_penalty": median_val,
        "canonical_expected": canonical,
        "deviation": deviation,
        "flag_deviation_gt_0_05": bool(deviation > 0.05),
        "seed_penalties": sub[["transpiler_seed", "penalty"]].to_dict(orient="records"),
    }
}

# broader sanity sweep: all identity-labelled (non-relabelled, non-complete) topology rows
identity_topologies = ["line_27", "cairo_heavy_hex_27"]
id_sub = attribution[attribution["topology"].isin(identity_topologies)]
grp = id_sub.groupby(["topology", "circuit_family", "logical_qubits", "optimization_level"])["penalty"].median()
sanity["identity_labelled_penalty_median_summary"] = {
    "n_groups": int(grp.shape[0]),
    "min_median": float(grp.min()),
    "max_median": float(grp.max()),
}

# ---------------------------------------------------------------------------
# Assemble mechanism_summary.json
# ---------------------------------------------------------------------------
summary = {
    "grid": {
        "attribution_rows": len(attribution),
        "label_invariance_L1_L3_rows": len(label_inv),
        "joined_rows": len(joined),
    },
    "classification_counts": class_counts,
    "contingency_full_classification_vs_label_invariant": {
        str(idx): row.to_dict() for idx, row in contingency_full.iterrows()
    },
    "contingency_vf2_solved_vs_label_invariant": {
        str(idx): row.to_dict() for idx, row in contingency_solved_vs_invariant.iterrows()
    },
    "contingency_vf2_failed_vs_systematic": {
        str(idx): row.to_dict() for idx, row in contingency_failed_vs_systematic.iterrows()
    },
    "exceptions": {
        "vf2_solved_but_not_label_invariant": exc_solved_not_invariant[
            ["base_topology", "circuit_family", "logical_qubits", "optimization_level",
             "n_solution_found", "n_no_solution_found", "n_trivial_sufficient",
             "label_invariant", "systematic", "relative_shift", "absolute_shift"]
        ].to_dict(orient="records"),
        "label_invariant_but_not_vf2_solved": exc_invariant_not_solved[
            ["base_topology", "circuit_family", "logical_qubits", "optimization_level",
             "classification", "n_solution_found", "n_no_solution_found", "n_trivial_sufficient",
             "label_invariant", "systematic"]
        ].to_dict(orient="records"),
        "vf2_failed_but_not_systematic": exc_failed_not_systematic[
            ["base_topology", "circuit_family", "logical_qubits", "optimization_level",
             "n_solution_found", "n_no_solution_found", "n_trivial_sufficient",
             "label_invariant", "systematic", "relative_shift", "absolute_shift"]
        ].to_dict(orient="records"),
        "systematic_but_not_vf2_failed": exc_systematic_not_failed[
            ["base_topology", "circuit_family", "logical_qubits", "optimization_level",
             "classification", "n_solution_found", "n_no_solution_found", "n_trivial_sufficient",
             "label_invariant", "systematic"]
        ].to_dict(orient="records"),
        "mixed_classification_rows": mixed_rows[
            ["base_topology", "circuit_family", "logical_qubits", "optimization_level",
             "per_topology_reason", "label_invariant", "systematic", "relative_shift"]
        ].to_dict(orient="records"),
        "trivial_sufficient_rows": trivial_rows[
            ["base_topology", "circuit_family", "logical_qubits", "optimization_level",
             "per_topology_reason", "label_invariant", "systematic"]
        ].to_dict(orient="records"),
        "base_vs_relabelled_verdict_disagreement": base_vs_relabelled_disagree.to_dict(orient="records"),
    },
    "claim_verification": claims,
    "sanity_check": sanity,
}

with open(f"{MECH_DIR}/mechanism_summary.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)

print(json.dumps(summary["classification_counts"], indent=2))
print("---contingency solved vs invariant---")
print(contingency_solved_vs_invariant)
print("---contingency failed vs systematic---")
print(contingency_failed_vs_systematic)
print("---exceptions counts---")
for k in ["vf2_solved_but_not_label_invariant", "label_invariant_but_not_vf2_solved",
          "vf2_failed_but_not_systematic", "systematic_but_not_vf2_failed",
          "mixed_classification_rows", "trivial_sufficient_rows"]:
    print(k, len(summary["exceptions"][k]))
print("base_vs_relabelled_verdict_disagreement:", len(base_vs_relabelled_disagree))
print("---claims---")
for k, v in claims.items():
    print(k, "PASS" if v["pass"] else "FAIL")
print("---sanity---")
print(json.dumps(sanity, indent=2, default=str))
