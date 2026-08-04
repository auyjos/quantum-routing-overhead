"""Controlled compilation: one shared basis, coupling maps only, fixed seeds."""

from __future__ import annotations

from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap, generate_preset_pass_manager

# Shared native basis for every topology, so connectivity is the only factor that changes.
BASIS_GATES = ("rz", "sx", "x", "cx")


def compile_circuit(
    circuit: QuantumCircuit,
    coupling_map: CouplingMap,
    optimization_level: int,
    seed_transpiler: int,
    basis_gates: tuple[str, ...] = BASIS_GATES,
) -> QuantumCircuit:
    """Compile `circuit` against `coupling_map` under the controlled settings."""
    if circuit.num_qubits > coupling_map.size():
        raise ValueError(
            f"circuit needs {circuit.num_qubits} logical qubits but the coupling map "
            f"has {coupling_map.size()} physical qubits"
        )
    pass_manager = generate_preset_pass_manager(
        optimization_level=optimization_level,
        basis_gates=list(basis_gates),
        coupling_map=coupling_map,
        seed_transpiler=seed_transpiler,
    )
    return pass_manager.run(circuit)


def unsupported_operations(
    circuit: QuantumCircuit, basis_gates: tuple[str, ...] = BASIS_GATES
) -> set[str]:
    """Operation names in `circuit` outside the allowed basis (barriers excepted)."""
    allowed = set(basis_gates) | {"barrier"}
    return {name for name in circuit.count_ops() if name not in allowed}


def coupling_violations(
    circuit: QuantumCircuit, coupling_map: CouplingMap
) -> list[tuple[int, int]]:
    """Two-qubit gate placements in `circuit` that the coupling map does not allow."""
    edges = set(coupling_map.get_edges())
    violations = []
    for instruction in circuit.data:
        if len(instruction.qubits) != 2 or instruction.operation.name == "barrier":
            continue
        pair = tuple(circuit.find_bit(bit).index for bit in instruction.qubits)
        if pair not in edges:
            violations.append(pair)
    return violations
