"""Compile the full grid once on complete_27 and write baseline.csv incrementally."""
from __future__ import annotations

import csv
import os

from routing_overhead.circuits import build_circuit, CIRCUIT_FAMILIES
from routing_overhead.transpilation import compile_circuit
from routing_overhead.metrics import circuit_metrics
from routing_overhead.topologies import build_coupling_map
from qiskit.transpiler import CouplingMap

FAMILIES = list(CIRCUIT_FAMILIES)
SIZES = [4, 8, 12, 16, 20, 24]
LEVELS = [0, 1, 3]
SEEDS = [11, 22, 33, 44, 55]

OUT_PATH = "/home/claude/work/artifacts/permsweep/baseline.csv"
FIELDS = [
    "circuit_family",
    "logical_qubits",
    "optimization_level",
    "transpiler_seed",
    "baseline_two_qubit_depth",
]


def already_done() -> set[tuple]:
    done = set()
    if not os.path.exists(OUT_PATH):
        return done
    with open(OUT_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            done.add(
                (
                    row["circuit_family"],
                    int(row["logical_qubits"]),
                    int(row["optimization_level"]),
                    int(row["transpiler_seed"]),
                )
            )
    return done


def main() -> None:
    # warm-up compile, not recorded
    warm_circuit = build_circuit("ghz_chain", 2)
    warm_map = CouplingMap.from_line(2)
    compile_circuit(warm_circuit, warm_map, optimization_level=1, seed_transpiler=0)

    done = already_done()
    write_header = not os.path.exists(OUT_PATH) or os.path.getsize(OUT_PATH) == 0
    coupling_map = build_coupling_map("complete_27")

    with open(OUT_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
            f.flush()
        count = 0
        for family in FAMILIES:
            for n in SIZES:
                circuit = build_circuit(family, n)
                for level in LEVELS:
                    for seed in SEEDS:
                        key = (family, n, level, seed)
                        if key in done:
                            continue
                        compiled = compile_circuit(
                            circuit, coupling_map, optimization_level=level, seed_transpiler=seed
                        )
                        metrics = circuit_metrics(compiled)
                        writer.writerow(
                            {
                                "circuit_family": family,
                                "logical_qubits": n,
                                "optimization_level": level,
                                "transpiler_seed": seed,
                                "baseline_two_qubit_depth": metrics["two_qubit_depth"],
                            }
                        )
                        count += 1
                        if count % 20 == 0:
                            f.flush()
        f.flush()
    print(f"baseline: wrote {count} new rows")


if __name__ == "__main__":
    main()
