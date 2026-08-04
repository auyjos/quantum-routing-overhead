"""Stage 1 tests for controlled compilation and the routing-overhead gate."""

import pytest

from routing_overhead.circuits import build_circuit, canonical_circuit_text
from routing_overhead.metrics import two_qubit_count, two_qubit_depth
from routing_overhead.topologies import build_coupling_map
from routing_overhead.transpilation import (
    BASIS_GATES,
    compile_circuit,
    coupling_violations,
    unsupported_operations,
)

TOPOLOGY_NAMES = ("complete_27", "line_27", "cairo_heavy_hex_27")


@pytest.mark.parametrize("topology", TOPOLOGY_NAMES)
@pytest.mark.parametrize("family", ["ghz_chain", "ghz_star", "qft", "efficient_su2"])
def test_output_uses_only_the_controlled_basis(topology, family):
    compiled = compile_circuit(
        build_circuit(family, 4),
        build_coupling_map(topology),
        optimization_level=1,
        seed_transpiler=11,
    )
    assert unsupported_operations(compiled, BASIS_GATES) == set()


@pytest.mark.parametrize("topology", TOPOLOGY_NAMES)
@pytest.mark.parametrize("family", ["ghz_chain", "ghz_star", "qft", "efficient_su2"])
def test_every_output_two_qubit_gate_respects_the_coupling_map(topology, family):
    coupling_map = build_coupling_map(topology)
    compiled = compile_circuit(
        build_circuit(family, 4),
        coupling_map,
        optimization_level=1,
        seed_transpiler=11,
    )
    assert coupling_violations(compiled, coupling_map) == []


def test_compilation_adds_no_measurements():
    compiled = compile_circuit(
        build_circuit("ghz_star", 4),
        build_coupling_map("line_27"),
        optimization_level=1,
        seed_transpiler=11,
    )
    assert "measure" not in compiled.count_ops()
    assert compiled.num_clbits == 0


def test_same_input_and_seed_produce_the_same_output():
    circuit = build_circuit("ghz_star", 8)
    coupling_map = build_coupling_map("line_27")
    outputs = [
        compile_circuit(circuit, coupling_map, optimization_level=1, seed_transpiler=33)
        for _ in range(2)
    ]
    assert canonical_circuit_text(outputs[0]) == canonical_circuit_text(outputs[1])


def test_complete_connectivity_needs_no_routing_for_a_four_qubit_ghz_star():
    compiled = compile_circuit(
        build_circuit("ghz_star", 4),
        build_coupling_map("complete_27"),
        optimization_level=1,
        seed_transpiler=11,
    )
    assert two_qubit_count(compiled) == 3
    assert two_qubit_depth(compiled) == 3


def test_line_connectivity_makes_a_four_qubit_ghz_star_cost_more():
    circuit = build_circuit("ghz_star", 4)
    complete = compile_circuit(
        circuit, build_coupling_map("complete_27"), optimization_level=1, seed_transpiler=11
    )
    line = compile_circuit(
        circuit, build_coupling_map("line_27"), optimization_level=1, seed_transpiler=11
    )
    assert two_qubit_count(line) > two_qubit_count(complete)
    assert two_qubit_depth(line) > two_qubit_depth(complete)


def test_invalid_optimization_level_is_rejected():
    with pytest.raises(ValueError):
        compile_circuit(
            build_circuit("ghz_chain", 4),
            build_coupling_map("line_27"),
            optimization_level=7,
            seed_transpiler=11,
        )


def test_circuit_wider_than_the_device_is_rejected():
    with pytest.raises(ValueError, match="28 logical qubits"):
        compile_circuit(
            build_circuit("ghz_chain", 28),
            build_coupling_map("line_27"),
            optimization_level=1,
            seed_transpiler=11,
        )
