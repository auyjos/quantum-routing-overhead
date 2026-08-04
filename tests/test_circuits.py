"""Stage 1 tests for deterministic circuit builders and circuit hashing."""

import pytest

from routing_overhead.circuits import (
    CIRCUIT_FAMILIES,
    build_circuit,
    circuit_hash,
    circuit_settings,
)


@pytest.mark.parametrize("family", CIRCUIT_FAMILIES)
@pytest.mark.parametrize("num_qubits", [4, 8])
def test_builder_returns_requested_logical_qubits(family, num_qubits):
    assert build_circuit(family, num_qubits).num_qubits == num_qubits


@pytest.mark.parametrize("family", CIRCUIT_FAMILIES)
def test_no_measurements_or_classical_bits(family):
    circuit = build_circuit(family, 6)
    assert circuit.num_clbits == 0
    assert "measure" not in circuit.count_ops()


@pytest.mark.parametrize("family", CIRCUIT_FAMILIES)
def test_no_unbound_parameters(family):
    assert len(build_circuit(family, 6).parameters) == 0


def test_ghz_chain_has_n_minus_one_cx_on_adjacent_logical_qubits():
    circuit = build_circuit("ghz_chain", 6)
    pairs = [
        tuple(circuit.find_bit(q).index for q in instruction.qubits)
        for instruction in circuit.data
        if instruction.operation.name == "cx"
    ]
    assert pairs == [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
    assert circuit.count_ops()["h"] == 1


def test_ghz_star_has_n_minus_one_cx_all_sharing_the_control():
    circuit = build_circuit("ghz_star", 6)
    pairs = [
        tuple(circuit.find_bit(q).index for q in instruction.qubits)
        for instruction in circuit.data
        if instruction.operation.name == "cx"
    ]
    assert pairs == [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5)]
    assert circuit.count_ops()["h"] == 1


def test_qft_omits_the_output_reversal_swap_network():
    circuit = build_circuit("qft", 6)
    assert "swap" not in circuit.count_ops()
    assert circuit_settings("qft", 6)["do_swaps"] is False


def test_efficient_su2_settings_are_recorded():
    settings = circuit_settings("efficient_su2", 6)
    assert settings["entanglement"] == "circular"
    assert settings["reps"] == 2
    assert settings["parameter_value"] == pytest.approx(0.5)


@pytest.mark.parametrize("family", CIRCUIT_FAMILIES)
def test_construction_is_deterministic(family):
    assert circuit_hash(build_circuit(family, 8)) == circuit_hash(build_circuit(family, 8))


@pytest.mark.parametrize("family", CIRCUIT_FAMILIES)
def test_hash_is_a_stable_hex_digest(family):
    digest = circuit_hash(build_circuit(family, 4))
    assert len(digest) == 64
    int(digest, 16)


def test_hash_separates_families_and_sizes():
    digests = {
        circuit_hash(build_circuit(family, size)) for family in CIRCUIT_FAMILIES for size in (4, 8)
    }
    assert len(digests) == 2 * len(CIRCUIT_FAMILIES)


def test_hash_tracks_gate_order():
    chain = build_circuit("ghz_chain", 4)
    reordered = chain.copy_empty_like()
    for instruction in reversed(chain.data):
        reordered.append(instruction)
    assert circuit_hash(chain) != circuit_hash(reordered)


def test_unknown_family_is_rejected():
    with pytest.raises(ValueError, match="unknown circuit family"):
        build_circuit("not_a_family", 4)
