"""Semantic equivalence checks for compiled circuits.

Kept to four logical qubits and small coupling maps on purpose: the unitary grows
exponentially, so this verifies the compiler contract rather than the 27-qubit grid.
"""

import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator
from qiskit.transpiler import CouplingMap

from routing_overhead.circuits import CIRCUIT_FAMILIES, build_circuit
from routing_overhead.transpilation import compile_circuit

SMALL_MAPS = {
    "full_4": CouplingMap.from_full(4, bidirectional=True),
    "line_4": CouplingMap.from_line(4, bidirectional=True),
}


@pytest.mark.parametrize("family", CIRCUIT_FAMILIES)
@pytest.mark.parametrize("coupling", sorted(SMALL_MAPS))
@pytest.mark.parametrize("optimization_level", [0, 1, 3])
def test_compiled_circuit_is_semantically_equivalent(family, coupling, optimization_level):
    circuit = build_circuit(family, 4)
    compiled = compile_circuit(
        circuit,
        SMALL_MAPS[coupling],
        optimization_level=optimization_level,
        seed_transpiler=11,
    )
    # `from_circuit` applies the transpiler's initial and final layouts.
    assert Operator.from_circuit(compiled).equiv(Operator(circuit))


def test_equivalence_assertion_has_teeth():
    circuit = build_circuit("ghz_star", 4)
    different = QuantumCircuit(4)
    different.x(0)
    assert not Operator(different).equiv(Operator(circuit))


def test_routing_changes_the_gate_sequence_but_not_the_semantics():
    circuit = build_circuit("ghz_star", 4)
    compiled = compile_circuit(
        circuit, SMALL_MAPS["line_4"], optimization_level=1, seed_transpiler=11
    )
    assert compiled.count_ops() != circuit.count_ops()
    assert Operator.from_circuit(compiled).equiv(Operator(circuit))
