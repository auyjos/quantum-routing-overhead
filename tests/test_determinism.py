"""Determinism contract.

Every experimental condition in this study is either a stored literal or a pure
function of its own name. Nothing is drawn from a process-level RNG, nothing depends on
dict or set iteration order, and nothing depends on how many times a helper has been
called. These tests fail loudly if that stops being true, because a study whose
conditions drift is not reproducible even when its code is unchanged.
"""

import subprocess
import sys
import textwrap

import pytest

from routing_overhead.circuits import build_circuit, circuit_hash
from routing_overhead.metrics import circuit_metrics
from routing_overhead.topologies import (
    PHYSICAL_QUBITS,
    RELABELLING_SWEEP_SIZE,
    SWEEP_BASES,
    SWEEP_TOPOLOGIES,
    apply_permutation,
    build_coupling_map,
    sweep_permutation,
    sweep_permutations_digest,
    topology_hash,
    undirected_edges,
)
from routing_overhead.transpilation import compile_circuit

# Pinned on 2026-08-18 from the SHA-256 derivation in `topologies.sweep_permutation`.
# This digest is the study's experimental conditions in one value: if the derivation
# changes in any way, every relabelling changes, every sweep number changes, and this
# test is the tripwire.
EXPECTED_SWEEP_DIGEST = "8fe63196a57332386ab1ecd50b2812eb499cd03196b0c60b70748142bd707293"


def test_the_sweep_permutation_digest_is_pinned():
    assert sweep_permutations_digest() == EXPECTED_SWEEP_DIGEST


def test_sweep_permutations_are_stable_across_processes():
    """A fresh interpreter must derive byte-identical permutations.

    Hash randomization (PYTHONHASHSEED) changes set and dict iteration order between
    processes. If any part of the derivation ever depended on that ordering, this test
    would catch it where a same-process check could not.
    """
    script = textwrap.dedent(
        """
        from routing_overhead.topologies import sweep_permutations_digest
        print(sweep_permutations_digest())
        """
    )
    seen = set()
    for hash_seed in ("0", "1", "12345"):
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": hash_seed, "PATH": "/usr/bin:/bin"},
        )
        seen.add(result.stdout.strip())
    assert seen == {EXPECTED_SWEEP_DIGEST}


def test_sweep_permutations_do_not_depend_on_call_order():
    """Each permutation is a pure function of (base, index), not of a shared stream."""
    forward = [
        sweep_permutation(base, index)
        for base in SWEEP_BASES
        for index in range(RELABELLING_SWEEP_SIZE)
    ]
    backward = [
        sweep_permutation(base, index)
        for base in reversed(SWEEP_BASES)
        for index in reversed(range(RELABELLING_SWEEP_SIZE))
    ]
    assert forward == list(reversed(backward))


@pytest.mark.parametrize("base", SWEEP_BASES)
def test_every_sweep_permutation_is_a_permutation(base):
    for index in range(RELABELLING_SWEEP_SIZE):
        permutation = sweep_permutation(base, index)
        assert sorted(permutation) == list(range(PHYSICAL_QUBITS))


def test_sweep_permutations_are_distinct():
    """Duplicates would silently shrink the sample without shrinking the reported n."""
    everything = [
        sweep_permutation(base, index)
        for base in SWEEP_BASES
        for index in range(RELABELLING_SWEEP_SIZE)
    ]
    assert len(set(everything)) == len(everything)


@pytest.mark.parametrize("name", SWEEP_TOPOLOGIES)
def test_sweep_topologies_preserve_the_graph(name):
    """A relabelling must rename nodes only: same edge count, same degree multiset."""
    from routing_overhead.topologies import base_topology

    base = base_topology(name)
    base_edges = undirected_edges(build_coupling_map(base))
    swept_edges = undirected_edges(build_coupling_map(name))
    assert len(swept_edges) == len(base_edges)

    def degrees(edges):
        counts: dict[int, int] = {}
        for a, b in edges:
            counts[a] = counts.get(a, 0) + 1
            counts[b] = counts.get(b, 0) + 1
        return sorted(counts.values())

    assert degrees(swept_edges) == degrees(base_edges)


def test_apply_permutation_rejects_a_non_bijection():
    """A collapsing map would quietly delete edges and change connectivity."""
    collapsing = [0] * PHYSICAL_QUBITS
    with pytest.raises(ValueError, match="not a bijection"):
        apply_permutation("line_27", collapsing)


@pytest.mark.parametrize(
    ("family", "num_qubits", "topology", "level", "seed"),
    [
        ("qft", 12, "line_27", 3, 11),
        ("ghz_star", 20, "cairo_heavy_hex_27", 1, 33),
        ("efficient_su2", 24, "line_27_perm07", 3, 55),
        ("ghz_chain", 16, "cairo_heavy_hex_27_relabelled", 0, 22),
    ],
)
def test_repeated_compilation_is_bit_identical(family, num_qubits, topology, level, seed):
    """The same inputs must produce the same compiled metrics, every time.

    SABRE is stochastic; `seed_transpiler` is what makes it a condition rather than a
    sample. If this ever fails, no penalty in the study is reproducible.
    """
    circuit = build_circuit(family, num_qubits)
    results = []
    for _ in range(3):
        compiled = compile_circuit(
            circuit,
            build_coupling_map(topology),
            optimization_level=level,
            seed_transpiler=seed,
        )
        results.append(tuple(sorted(circuit_metrics(compiled).items())))
    assert len(set(results)) == 1


def test_circuit_and_topology_hashes_are_stable_within_a_process():
    """The join keys that match a constrained run to its baseline must not drift."""
    for family, num_qubits in (("qft", 8), ("efficient_su2", 12)):
        first = circuit_hash(build_circuit(family, num_qubits))
        second = circuit_hash(build_circuit(family, num_qubits))
        assert first == second
    for name in ("line_27", "cairo_heavy_hex_27_perm03"):
        assert topology_hash(build_coupling_map(name)) == topology_hash(
            build_coupling_map(name)
        )


def test_distinct_labellings_get_distinct_topology_hashes():
    """Same graph, different labelling: the provenance record must tell them apart."""
    hashes = {
        name: topology_hash(build_coupling_map(name))
        for name in ("line_27", "line_27_relabelled", *SWEEP_TOPOLOGIES[:6])
    }
    assert len(set(hashes.values())) == len(hashes)


@pytest.mark.parametrize("theta", [0.1, 0.7853981633974483, 2.5])
def test_efficient_su2_routing_does_not_depend_on_its_parameter_value(theta):
    """The study binds every Efficient SU(2) angle to a single value.

    At level 3 `ConsolidateBlocks` and `Split2QUnitaries` resynthesise two-qubit blocks,
    so a parameter-dependent result would make the SU(2) numbers a one-instance finding
    rather than a structural one. Routing metrics are compared against the study's own
    binding; a full sweep over six angles (including pi/4) showed zero deviation.
    """
    from qiskit.circuit.library import efficient_su2

    from routing_overhead.circuits import (
        SU2_ENTANGLEMENT,
        SU2_PARAMETER_VALUE,
        SU2_REPS,
        build_circuit,
    )

    def metrics(value):
        circuit = efficient_su2(num_qubits=12, entanglement=SU2_ENTANGLEMENT, reps=SU2_REPS)
        circuit = circuit.assign_parameters({p: value for p in circuit.parameters})
        compiled = compile_circuit(
            circuit,
            build_coupling_map("line_27"),
            optimization_level=3,
            seed_transpiler=11,
        )
        return circuit_metrics(compiled)["two_qubit_depth"]

    assert metrics(theta) == metrics(SU2_PARAMETER_VALUE)
    # and the study's own builder agrees with an explicit binding at that value
    reference = compile_circuit(
        build_circuit("efficient_su2", 12),
        build_coupling_map("line_27"),
        optimization_level=3,
        seed_transpiler=11,
    )
    assert circuit_metrics(reference)["two_qubit_depth"] == metrics(SU2_PARAMETER_VALUE)
