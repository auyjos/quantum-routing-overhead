"""Stage 1 tests for primitive circuit metrics, using hand-built known circuits."""

from qiskit import QuantumCircuit

from routing_overhead.metrics import (
    circuit_metrics,
    is_two_qubit,
    total_depth,
    two_qubit_count,
    two_qubit_depth,
)


def test_empty_circuit_has_zero_metrics():
    circuit = QuantumCircuit(4)
    assert total_depth(circuit) == 0
    assert two_qubit_depth(circuit) == 0
    assert two_qubit_count(circuit) == 0


def test_single_cx_has_two_qubit_depth_one():
    circuit = QuantumCircuit(2)
    circuit.cx(0, 1)
    assert total_depth(circuit) == 1
    assert two_qubit_depth(circuit) == 1
    assert two_qubit_count(circuit) == 1


def test_parallel_two_qubit_gates_have_two_qubit_depth_one():
    circuit = QuantumCircuit(4)
    circuit.cx(0, 1)
    circuit.cx(2, 3)
    assert two_qubit_depth(circuit) == 1
    assert two_qubit_count(circuit) == 2


def test_sequential_two_qubit_gates_sharing_a_qubit_have_two_qubit_depth_two():
    circuit = QuantumCircuit(3)
    circuit.cx(0, 1)
    circuit.cx(1, 2)
    assert two_qubit_depth(circuit) == 2
    assert two_qubit_count(circuit) == 2


def test_single_qubit_gates_are_excluded_from_two_qubit_depth():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.x(1)
    circuit.cx(0, 1)
    circuit.h(0)
    assert total_depth(circuit) == 3
    assert two_qubit_depth(circuit) == 1
    assert two_qubit_count(circuit) == 1


def test_two_qubit_count_is_gate_name_agnostic():
    circuit = QuantumCircuit(4)
    circuit.cx(0, 1)
    circuit.cz(1, 2)
    circuit.swap(2, 3)
    circuit.ecr(0, 3)
    circuit.h(0)
    assert two_qubit_count(circuit) == 4


def test_is_two_qubit_selects_only_two_qubit_instructions():
    circuit = QuantumCircuit(3)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.ccx(0, 1, 2)
    assert [is_two_qubit(instruction) for instruction in circuit.data] == [False, True, False]


def test_circuit_metrics_bundles_the_three_primitives():
    circuit = QuantumCircuit(3)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.cx(1, 2)
    assert circuit_metrics(circuit) == {
        "depth": 3,
        "two_qubit_depth": 2,
        "two_qubit_count": 2,
    }
