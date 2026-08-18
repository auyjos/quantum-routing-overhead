"""Instrument the transpiler to attribute the label-permutation effect to VF2Layout.

Grid: 4 constrained topologies x 4 circuit families x 6 sizes x 2 levels x 5 seeds = 960
compilations, each run through generate_preset_pass_manager with a callback that records
layout provenance (VF2Layout stop reason at the moment the pass runs and its final value,
plus the CheckMap results and the final layout). complete_27 is compiled on the same
(family, size, level, seed) grid (240 unique combinations -- shared as the penalty
baseline for both the base and relabelled variant of a topology, since JOIN_KEYS in
routing_overhead.aggregation do not include topology) to compute two_qubit_depth penalties.
"""
from __future__ import annotations

import itertools
import json
import time

import pandas as pd
from qiskit.transpiler import generate_preset_pass_manager
from qiskit.transpiler.passes.layout.vf2_layout import VF2LayoutStopReason

from routing_overhead.circuits import build_circuit, circuit_hash
from routing_overhead.metrics import two_qubit_depth
from routing_overhead.topologies import build_coupling_map
from routing_overhead.transpilation import BASIS_GATES

TOPOLOGIES = [
    "line_27",
    "line_27_relabelled",
    "cairo_heavy_hex_27",
    "cairo_heavy_hex_27_relabelled",
]
FAMILIES = ["qft", "ghz_chain", "ghz_star", "efficient_su2"]
SIZES = [4, 8, 12, 16, 20, 24]
LEVELS = [1, 3]
SEEDS = [11, 22, 33, 44, 55]

OUT_DIR = "/home/claude/work/artifacts/mechanism"


def compile_with_provenance(circuit, coupling_map, level, seed):
    """Run the preset pass manager with a callback capturing layout provenance.

    `CheckMap` writes its boolean result under different property-set keys depending
    on where it sits in the preset pipeline: the level-1 pipeline runs
    TrivialLayout -> CheckMap (key "is_swap_mapped") -> [VF2Layout only if not already
    mapped] -> ApplyLayout -> CheckMap (key "routing_not_needed") -> [routing only if
    needed]; level 3 has no TrivialLayout/pre-check stage at all, so "is_swap_mapped"
    is never set there and VF2Layout always runs. Rather than assume ordinal position,
    both keys are read fresh from `property_set` on every callback firing, so the
    recorded value is always whatever the pipeline last wrote (or None if that stage
    never ran for this level).
    """
    prov = {
        "vf2_stop_reason_at_vf2layout": None,  # value observed right when VF2Layout ran
        "vf2_stop_reason_final": None,  # value observed at the very last callback firing
        "trivial_check_map_is_swap_mapped": None,  # "is_swap_mapped": trivial layout already valid? (level 1 only)
        "routing_not_needed": None,  # "routing_not_needed": final chosen layout needs no SWAP routing?
        "vf2layout_ran": False,
        "sabre_layout_ran": False,
        "vf2_post_layout_ran": False,
        "final_layout_repr": None,
        "pass_sequence": [],
    }

    def cb(pass_=None, property_set=None, **kwargs):
        name = pass_.__class__.__name__
        prov["pass_sequence"].append(name)
        if name == "VF2Layout":
            prov["vf2layout_ran"] = True
            reason = property_set.get("VF2Layout_stop_reason")
            prov["vf2_stop_reason_at_vf2layout"] = reason.name if reason is not None else None
        if name == "SabreLayout":
            prov["sabre_layout_ran"] = True
        if name == "VF2PostLayout":
            prov["vf2_post_layout_ran"] = True
        reason_final = property_set.get("VF2Layout_stop_reason")
        prov["vf2_stop_reason_final"] = reason_final.name if reason_final is not None else None
        if property_set.get("is_swap_mapped") is not None:
            prov["trivial_check_map_is_swap_mapped"] = property_set.get("is_swap_mapped")
        if property_set.get("routing_not_needed") is not None:
            prov["routing_not_needed"] = property_set.get("routing_not_needed")
        layout = property_set.get("layout")
        if layout is not None:
            try:
                pairs = sorted(
                    (circuit.find_bit(qubit).index, physical)
                    for qubit, physical in layout.get_virtual_bits().items()
                )
                prov["final_layout_repr"] = str(pairs)
            except Exception:
                prov["final_layout_repr"] = repr(layout).replace("\n", " ")

    pm = generate_preset_pass_manager(
        optimization_level=level,
        basis_gates=list(BASIS_GATES),
        coupling_map=coupling_map,
        seed_transpiler=seed,
    )
    t0 = time.time()
    out = pm.run(circuit, callback=cb)
    prov["compile_time_seconds"] = time.time() - t0
    prov["output_two_qubit_depth"] = two_qubit_depth(out)
    return prov


def main():
    complete_cm = build_coupling_map("complete_27")

    # Baseline: complete_27, deduped over (family, size, level, seed) -- 240 unique combos.
    # Shared as the penalty denominator for both base and relabelled variants of a
    # topology (JOIN_KEYS in aggregation.py do not include topology), so this covers the
    # 480 complete_27 compilations described in the task (240 for the line pair's context,
    # 240 for the cairo pair's context, both numerically identical to this dedup table).
    baseline = {}
    baseline_rows = []
    for family, size, level, seed in itertools.product(FAMILIES, SIZES, LEVELS, SEEDS):
        circuit = build_circuit(family, size)
        chash = circuit_hash(circuit)
        out = None
        pm = generate_preset_pass_manager(
            optimization_level=level,
            basis_gates=list(BASIS_GATES),
            coupling_map=complete_cm,
            seed_transpiler=seed,
        )
        out = pm.run(circuit)
        depth = two_qubit_depth(out)
        key = (family, size, level, seed)
        baseline[key] = depth
        baseline_rows.append(
            {
                "circuit_family": family,
                "logical_qubits": size,
                "optimization_level": level,
                "transpiler_seed": seed,
                "circuit_hash": chash,
                "baseline_two_qubit_depth": depth,
            }
        )
    pd.DataFrame(baseline_rows).to_csv(f"{OUT_DIR}/complete_27_baseline.csv", index=False)
    print(f"baseline compiled: {len(baseline_rows)} rows (expected 240 unique; "
          f"represents 480 complete_27 compilations per the task's per-pair accounting)")

    rows = []
    n_total = len(TOPOLOGIES) * len(FAMILIES) * len(SIZES) * len(LEVELS) * len(SEEDS)
    i = 0
    for topology in TOPOLOGIES:
        cm = build_coupling_map(topology)
        for family, size, level, seed in itertools.product(FAMILIES, SIZES, LEVELS, SEEDS):
            i += 1
            circuit = build_circuit(family, size)
            chash = circuit_hash(circuit)
            prov = compile_with_provenance(circuit, cm, level, seed)
            key = (family, size, level, seed)
            base_depth = baseline[key]
            penalty = (
                prov["output_two_qubit_depth"] / base_depth if base_depth > 0 else float("nan")
            )
            row = {
                "topology": topology,
                "circuit_family": family,
                "logical_qubits": size,
                "optimization_level": level,
                "transpiler_seed": seed,
                "circuit_hash": chash,
                "vf2_stop_reason": prov["vf2_stop_reason_at_vf2layout"],
                "vf2_stop_reason_final": prov["vf2_stop_reason_final"],
                "vf2layout_ran": prov["vf2layout_ran"],
                "trivial_check_map_is_swap_mapped": prov["trivial_check_map_is_swap_mapped"],
                "routing_not_needed": prov["routing_not_needed"],
                "sabre_layout_ran": prov["sabre_layout_ran"],
                "vf2_post_layout_ran": prov["vf2_post_layout_ran"],
                "output_two_qubit_depth": prov["output_two_qubit_depth"],
                "baseline_two_qubit_depth": base_depth,
                "penalty": penalty,
                "compile_time_seconds": prov["compile_time_seconds"],
                "final_layout": prov["final_layout_repr"],
            }
            rows.append(row)
            if i % 100 == 0:
                print(f"{i}/{n_total}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT_DIR}/attribution.csv", index=False)
    print(f"wrote {len(df)} rows to {OUT_DIR}/attribution.csv")

    # sanity: check reason values are only the known enum names or None
    print(df["vf2_stop_reason"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
