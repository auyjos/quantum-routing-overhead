"""Join raw.csv with baseline.csv to compute two_qubit_depth_penalty, write penalties.csv."""
from __future__ import annotations

import csv

ROOT = "/home/claude/work/artifacts/permsweep"

with open(f"{ROOT}/baseline.csv", newline="") as f:
    baseline_rows = list(csv.DictReader(f))

baseline = {}
for row in baseline_rows:
    key = (
        row["circuit_family"],
        int(row["logical_qubits"]),
        int(row["optimization_level"]),
        int(row["transpiler_seed"]),
    )
    baseline[key] = int(row["baseline_two_qubit_depth"])

with open(f"{ROOT}/raw.csv", newline="") as f:
    raw_rows = list(csv.DictReader(f))

out_fields = [
    "base_topology",
    "labeling_id",
    "circuit_family",
    "logical_qubits",
    "optimization_level",
    "transpiler_seed",
    "output_two_qubit_depth",
    "baseline_two_qubit_depth",
    "two_qubit_depth_penalty",
]

zero_or_nan = []
out_rows = []
for row in raw_rows:
    key = (
        row["circuit_family"],
        int(row["logical_qubits"]),
        int(row["optimization_level"]),
        int(row["transpiler_seed"]),
    )
    base_val = baseline[key]
    out_val = int(row["output_two_qubit_depth"])
    if base_val == 0:
        zero_or_nan.append((row["base_topology"], row["labeling_id"], key))
        penalty = float("nan")
    else:
        penalty = out_val / base_val
    out_rows.append(
        {
            "base_topology": row["base_topology"],
            "labeling_id": row["labeling_id"],
            "circuit_family": row["circuit_family"],
            "logical_qubits": row["logical_qubits"],
            "optimization_level": row["optimization_level"],
            "transpiler_seed": row["transpiler_seed"],
            "output_two_qubit_depth": out_val,
            "baseline_two_qubit_depth": base_val,
            "two_qubit_depth_penalty": penalty,
        }
    )

with open(f"{ROOT}/penalties.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=out_fields)
    writer.writeheader()
    writer.writerows(out_rows)

print(f"rows written: {len(out_rows)}")
print(f"zero baseline denominators: {len(zero_or_nan)}")
if zero_or_nan:
    print(zero_or_nan[:10])
