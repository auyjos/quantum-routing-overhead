"""Sweep random relabellings of line_27 / cairo_heavy_hex_27 and compile the full grid
for each labeling, appending incrementally to raw.csv. Resumable: skips labeling_ids
already fully present in raw.csv for a given base_topology.
"""
from __future__ import annotations

import csv
import json
import os

from routing_overhead.circuits import build_circuit, CIRCUIT_FAMILIES
from routing_overhead.transpilation import compile_circuit
from routing_overhead.metrics import circuit_metrics
from routing_overhead.topologies import build_coupling_map, undirected_edges, PERMUTATIONS
from qiskit.transpiler import CouplingMap

FAMILIES = list(CIRCUIT_FAMILIES)
SIZES = [4, 8, 12, 16, 20, 24]
LEVELS = [0, 1, 3]
SEEDS = [11, 22, 33, 44, 55]
GRID_SIZE = len(FAMILIES) * len(SIZES) * len(LEVELS) * len(SEEDS)  # 360

BASES = ["line_27", "cairo_heavy_hex_27"]

ROOT = "/home/claude/work/artifacts/permsweep"
RAW_PATH = os.path.join(ROOT, "raw.csv")
PERM_PATH = os.path.join(ROOT, "permutations.json")

FIELDS = [
    "base_topology",
    "labeling_id",
    "circuit_family",
    "logical_qubits",
    "optimization_level",
    "transpiler_seed",
    "output_two_qubit_depth",
]


def load_random_perms() -> dict:
    with open(PERM_PATH) as f:
        return json.load(f)


def labeling_ids() -> list[str]:
    return ["identity", "stored"] + [f"r{i:02d}" for i in range(24)]


def edges_for_labeling(base: str, labeling: str, base_edges, random_perms) -> list[tuple[int, int]]:
    if labeling == "identity":
        return list(base_edges)
    if labeling == "stored":
        perm = PERMUTATIONS[base]
    else:
        idx = int(labeling[1:])
        perm = random_perms[base][idx]
    return [tuple(sorted((perm[a], perm[b]))) for a, b in base_edges]


def build_labeled_coupling_map(edges: list[tuple[int, int]]) -> CouplingMap:
    directed = [[a, b] for a, b in edges] + [[b, a] for a, b in edges]
    return CouplingMap(couplinglist=directed)


def completed_counts() -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    if not os.path.exists(RAW_PATH):
        return counts
    with open(RAW_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["base_topology"], row["labeling_id"])
            counts[key] = counts.get(key, 0) + 1
    return counts


def main() -> None:
    # warm-up compile, not recorded
    warm_circuit = build_circuit("ghz_chain", 2)
    warm_map = CouplingMap.from_line(2)
    compile_circuit(warm_circuit, warm_map, optimization_level=1, seed_transpiler=0)

    random_perms = load_random_perms()
    counts = completed_counts()
    write_header = not os.path.exists(RAW_PATH) or os.path.getsize(RAW_PATH) == 0

    # pre-build circuits once per (family, size)
    circuits = {(fam, n): build_circuit(fam, n) for fam in FAMILIES for n in SIZES}

    total_written = 0
    with open(RAW_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
            f.flush()

        for base in BASES:
            base_edges = undirected_edges(build_coupling_map(base))
            for labeling in labeling_ids():
                key = (base, labeling)
                if counts.get(key, 0) >= GRID_SIZE:
                    print(f"skip {base}/{labeling}: already complete ({counts.get(key)})")
                    continue
                edges = edges_for_labeling(base, labeling, base_edges, random_perms)
                coupling_map = build_labeled_coupling_map(edges)

                # If partially done (shouldn't normally happen since we write per full
                # labeling chunk, but guard anyway) - recompute the whole labeling to
                # keep it simple & correct, first purging partial rows.
                if 0 < counts.get(key, 0) < GRID_SIZE:
                    _purge_partial(base, labeling)

                rows_written = 0
                for family in FAMILIES:
                    for n in SIZES:
                        circuit = circuits[(family, n)]
                        for level in LEVELS:
                            for seed in SEEDS:
                                compiled = compile_circuit(
                                    circuit,
                                    coupling_map,
                                    optimization_level=level,
                                    seed_transpiler=seed,
                                )
                                metrics = circuit_metrics(compiled)
                                writer.writerow(
                                    {
                                        "base_topology": base,
                                        "labeling_id": labeling,
                                        "circuit_family": family,
                                        "logical_qubits": n,
                                        "optimization_level": level,
                                        "transpiler_seed": seed,
                                        "output_two_qubit_depth": metrics["two_qubit_depth"],
                                    }
                                )
                                rows_written += 1
                    f.flush()
                total_written += rows_written
                print(f"done {base}/{labeling}: {rows_written} rows")
    print(f"sweep: wrote {total_written} new rows this invocation")


def _purge_partial(base: str, labeling: str) -> None:
    """Remove any partial rows for (base, labeling) from raw.csv before redoing it."""
    with open(RAW_PATH, newline="") as f:
        reader = csv.DictReader(f)
        rows = [
            row
            for row in reader
            if not (row["base_topology"] == base and row["labeling_id"] == labeling)
        ]
    with open(RAW_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
