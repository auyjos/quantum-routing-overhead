"""Deterministic circuit builders and stable circuit hashing.

Every builder returns a bare `QuantumCircuit` with no measurements, no classical
bits, and no unbound parameters, so the same logical circuit instance can be sent
to every topology under test.
"""

from __future__ import annotations

import hashlib

from qiskit import QuantumCircuit
from qiskit.circuit.library import efficient_su2
from qiskit.synthesis import synth_qft_full

CIRCUIT_FAMILIES = ("qft", "ghz_chain", "ghz_star", "efficient_su2")

# Fixed because the study is about topology and compilation, not variational tuning.
SU2_PARAMETER_VALUE = 0.5
SU2_ENTANGLEMENT = "circular"
SU2_REPS = 2


def build_circuit(family: str, num_qubits: int) -> QuantumCircuit:
    """Build the logical circuit for `family` on `num_qubits` logical qubits."""
    if family not in CIRCUIT_FAMILIES:
        raise ValueError(f"unknown circuit family: {family!r}; expected one of {CIRCUIT_FAMILIES}")
    if num_qubits < 2:
        raise ValueError(f"num_qubits must be at least 2, got {num_qubits}")

    if family == "qft":
        return _build_qft(num_qubits)
    if family == "ghz_chain":
        return _build_ghz_chain(num_qubits)
    if family == "ghz_star":
        return _build_ghz_star(num_qubits)
    return _build_efficient_su2(num_qubits)


def circuit_settings(family: str, num_qubits: int) -> dict:
    """Generation settings recorded alongside every circuit."""
    if family not in CIRCUIT_FAMILIES:
        raise ValueError(f"unknown circuit family: {family!r}; expected one of {CIRCUIT_FAMILIES}")
    settings: dict = {"family": family, "num_qubits": num_qubits}
    if family == "qft":
        # No final output-reversal network: algorithm SWAPs would contaminate routing overhead.
        settings["do_swaps"] = False
    elif family == "efficient_su2":
        settings["entanglement"] = SU2_ENTANGLEMENT
        settings["reps"] = SU2_REPS
        settings["parameter_value"] = SU2_PARAMETER_VALUE
    return settings


def canonical_circuit_text(circuit: QuantumCircuit) -> str:
    """Stable textual serialization: qubit width plus one line per instruction."""
    lines = [f"qubits={circuit.num_qubits}", f"clbits={circuit.num_clbits}"]
    for instruction in circuit.data:
        qubits = ",".join(str(circuit.find_bit(bit).index) for bit in instruction.qubits)
        clbits = ",".join(str(circuit.find_bit(bit).index) for bit in instruction.clbits)
        params = ",".join(_format_parameter(param) for param in instruction.operation.params)
        lines.append(f"{instruction.operation.name}({params})[{qubits}][{clbits}]")
    return "\n".join(lines)


def circuit_hash(circuit: QuantumCircuit) -> str:
    """SHA-256 of the canonical serialization, used to prove topologies shared an input."""
    return hashlib.sha256(canonical_circuit_text(circuit).encode("utf-8")).hexdigest()


def _format_parameter(param) -> str:
    try:
        return f"{float(param):.12g}"
    except (TypeError, ValueError):
        return repr(param)


def _build_qft(num_qubits: int) -> QuantumCircuit:
    return synth_qft_full(num_qubits=num_qubits, do_swaps=False)


def _build_ghz_chain(num_qubits: int) -> QuantumCircuit:
    circuit = QuantumCircuit(num_qubits)
    circuit.h(0)
    for qubit in range(num_qubits - 1):
        circuit.cx(qubit, qubit + 1)
    return circuit


def _build_ghz_star(num_qubits: int) -> QuantumCircuit:
    circuit = QuantumCircuit(num_qubits)
    circuit.h(0)
    for qubit in range(1, num_qubits):
        circuit.cx(0, qubit)
    return circuit


def _build_efficient_su2(num_qubits: int) -> QuantumCircuit:
    circuit = efficient_su2(
        num_qubits=num_qubits,
        entanglement=SU2_ENTANGLEMENT,
        reps=SU2_REPS,
    )
    return circuit.assign_parameters(
        {parameter: SU2_PARAMETER_VALUE for parameter in circuit.parameters}
    )
