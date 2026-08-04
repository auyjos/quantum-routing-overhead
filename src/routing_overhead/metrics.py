"""Primitive circuit metrics extracted from input and compiled circuits."""

from __future__ import annotations

from qiskit import QuantumCircuit
from qiskit.circuit import CircuitInstruction


def is_two_qubit(instruction: CircuitInstruction) -> bool:
    """True for any instruction acting on exactly two qubits, whatever its name."""
    return len(instruction.qubits) == 2


def total_depth(circuit: QuantumCircuit) -> int:
    return circuit.depth()


def two_qubit_depth(circuit: QuantumCircuit) -> int:
    return circuit.depth(filter_function=is_two_qubit)


def two_qubit_count(circuit: QuantumCircuit) -> int:
    return sum(1 for instruction in circuit.data if is_two_qubit(instruction))


def circuit_metrics(circuit: QuantumCircuit) -> dict:
    return {
        "depth": total_depth(circuit),
        "two_qubit_depth": two_qubit_depth(circuit),
        "two_qubit_count": two_qubit_count(circuit),
    }
