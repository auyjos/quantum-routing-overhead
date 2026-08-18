"""Controlled 27-qubit connectivity models and their descriptive graph metadata.

Only coupling maps are handed to the transpiler: a full backend `Target` would
carry native gates, directionality and calibration data, which would confound
topology with hardware configuration. NetworkX is used for descriptive metrics
only.
"""

from __future__ import annotations

import functools
import hashlib

import networkx as nx
from qiskit.transpiler import CouplingMap

PHYSICAL_QUBITS = 27

BASE_TOPOLOGIES = ("complete_27", "line_27", "cairo_heavy_hex_27")

# Label-permutation controls. Each is the SAME GRAPH as its base topology with the
# physical-qubit labels permuted, so every connectivity property the study reports —
# edge count, degree sequence, diameter, mean shortest path — is identical by
# construction, and the only thing that changes is which physical index each node
# carries.
#
# The control exists because `TrivialLayout` (the level-0 initial layout, and the first
# candidate tried at level 1) maps logical qubit i to physical qubit i. The circuit
# builders index the GHZ chain and the circular Efficient SU(2) entangler on `(i, i+1)`,
# which is exactly how `CouplingMap.from_line(27)` numbers its nodes. Any penalty that
# moves when only the labels move was measuring that index alignment rather than
# connectivity. A level whose results are unchanged under relabelling is label-invariant
# and can be compared across topologies without that confound.
RELABELLED_SUFFIX = "_relabelled"

# The named single control: a stored derangement chosen so that no identity-aligned
# `(i, i+1)` pair survives as an edge, i.e. the strongest possible removal of the
# confound for a chain-shaped circuit.
RELABELLED_BASES = {
    "line_27" + RELABELLED_SUFFIX: "line_27",
    "cairo_heavy_hex_27" + RELABELLED_SUFFIX: "cairo_heavy_hex_27",
}

# The sweep: a family of relabellings per base, so the labelling effect is reported as a
# distribution rather than a single anecdote. One permutation answers "does labelling
# matter here?"; a family answers "is this study's labelling typical?".
RELABELLING_SWEEP_SIZE = 24
SWEEP_PREFIX = "_perm"

SWEEP_BASES = tuple(RELABELLED_BASES.values())

# Permutations are stored as literals rather than regenerated from a seeded shuffle:
# the exact relabelling is part of the experimental record, and it must not drift with
# the Python version that happens to run the study. Each was selected by the
# deterministic search in `tests/test_topologies.py`, which re-derives and re-checks the
# two properties that make it a valid control:
#   1. it is a permutation of 0..26 with no fixed point, and
#   2. no identity-aligned consecutive pair (i, i+1) survives as an edge,
# so `TrivialLayout` satisfies zero of the chain's required interactions.
PERMUTATIONS = {
    "line_27": (
        6, 20, 3, 1, 13, 8, 18, 10, 0, 5, 12, 24, 26,
        17, 4, 21, 25, 11, 9, 22, 16, 2, 15, 19, 23, 7, 14,
    ),
    "cairo_heavy_hex_27": (
        11, 13, 6, 24, 16, 7, 21, 0, 17, 5, 2, 9, 8,
        26, 23, 3, 12, 25, 22, 20, 15, 19, 18, 4, 14, 10, 1,
    ),
}

def sweep_topology(base: str, index: int) -> str:
    """Canonical name of the `index`-th sweep relabelling of `base`."""
    if base not in SWEEP_BASES:
        raise ValueError(f"no relabelling sweep defined for topology: {base!r}")
    if not 0 <= index < RELABELLING_SWEEP_SIZE:
        raise ValueError(
            f"sweep index must be in 0..{RELABELLING_SWEEP_SIZE - 1}, got {index}"
        )
    return f"{base}{SWEEP_PREFIX}{index:02d}"


SWEEP_TOPOLOGIES = tuple(
    sweep_topology(base, index)
    for base in SWEEP_BASES
    for index in range(RELABELLING_SWEEP_SIZE)
)

SWEEP_BASE_OF = {
    sweep_topology(base, index): base
    for base in SWEEP_BASES
    for index in range(RELABELLING_SWEEP_SIZE)
}

TOPOLOGIES = (*BASE_TOPOLOGIES, *RELABELLED_BASES, *SWEEP_TOPOLOGIES)


def base_topology(name: str) -> str:
    """The graph a topology is built from: itself, or the base a control relabels."""
    if name in RELABELLED_BASES:
        return RELABELLED_BASES[name]
    return SWEEP_BASE_OF.get(name, name)


def is_relabelled(name: str) -> bool:
    """True for any label-permutation control: the named one or a sweep member."""
    return name in RELABELLED_BASES or name in SWEEP_BASE_OF


def is_sweep(name: str) -> bool:
    """True only for members of the relabelling sweep."""
    return name in SWEEP_BASE_OF


def sweep_index(name: str) -> int | None:
    """Position of `name` within its base's sweep, or None if it is not a sweep member."""
    if name not in SWEEP_BASE_OF:
        return None
    return int(name.rsplit(SWEEP_PREFIX, 1)[1])


def build_coupling_map(name: str) -> CouplingMap:
    """Return a fresh, bidirectional `CouplingMap` for `name`.

    A new object is built on every call so runs can never mutate a shared map.
    """
    if name not in TOPOLOGIES:
        raise ValueError(
            f"unknown topology: {name!r}; expected one of {BASE_TOPOLOGIES}, "
            f"{tuple(RELABELLED_BASES)}, or a relabelling-sweep member"
        )
    if name in SWEEP_BASE_OF:
        base = SWEEP_BASE_OF[name]
        return _symmetrized(apply_permutation(base, sweep_permutation(base, sweep_index(name))))
    if name in RELABELLED_BASES:
        base = RELABELLED_BASES[name]
        return _symmetrized(relabelled_edges(base))
    if name == "complete_27":
        return CouplingMap.from_full(PHYSICAL_QUBITS, bidirectional=True)
    if name == "line_27":
        return CouplingMap.from_line(PHYSICAL_QUBITS, bidirectional=True)
    return _symmetrized(_cairo_undirected_edges())


def relabelled_edges(base: str) -> tuple[tuple[int, int], ...]:
    """Undirected edges of `base` with its stored physical-qubit permutation applied."""
    if base not in PERMUTATIONS:
        raise ValueError(f"no stored permutation for topology: {base!r}")
    return apply_permutation(base, PERMUTATIONS[base])


def apply_permutation(base: str, permutation) -> tuple[tuple[int, int], ...]:
    """Undirected edges of `base` relabelled by `permutation`.

    The graph is unchanged: this renames nodes, it does not add or remove edges.
    """
    edges = undirected_edges(build_coupling_map(base))
    relabelled = tuple(
        sorted({tuple(sorted((permutation[a], permutation[b]))) for a, b in edges})
    )
    if len(relabelled) != len(edges):
        raise ValueError(
            f"relabelling {base!r} changed the edge count "
            f"({len(edges)} -> {len(relabelled)}); the permutation is not a bijection"
        )
    return relabelled


def _keystream(label: str):
    """Endless deterministic byte stream derived from `label` via SHA-256.

    Python's `random` module is deliberately not used. Its Mersenne Twister output is
    stable in CPython today but is an implementation detail, not a specification, so a
    study that derived its experimental conditions from it would be reproducible only
    by accident. SHA-256 is specified, so these permutations are identical on every
    Python version, platform and interpreter, forever.
    """
    counter = 0
    while True:
        block = hashlib.sha256(f"{label}|{counter}".encode()).digest()
        yield from block
        counter += 1


def _uniform_below(stream, bound: int) -> int:
    """Uniform integer in [0, bound) from a byte stream, by rejection sampling.

    Rejection rather than modulo: a modulo fold would bias the low indices, and the
    sweep is described as drawing uniformly from the relabellings, so the derivation
    has to actually be uniform rather than nearly so.
    """
    if bound <= 1:
        return 0
    span = 1
    width = 0
    while span < bound:
        span <<= 8
        width += 1
    limit = span - (span % bound)
    while True:
        value = int.from_bytes(bytes(next(stream) for _ in range(width)), "big")
        if value < limit:
            return value % bound


def sweep_permutation(base: str, index: int) -> tuple[int, ...]:
    """The `index`-th sweep permutation for `base`, derived deterministically.

    Fisher-Yates driven by a SHA-256 keystream keyed on the topology name and the sweep
    index, so every permutation is a pure function of its own identity — reproducible
    without shipping run data, and independent of iteration order elsewhere.
    """
    if base not in SWEEP_BASES:
        raise ValueError(f"no relabelling sweep defined for topology: {base!r}")
    if not 0 <= index < RELABELLING_SWEEP_SIZE:
        raise ValueError(
            f"sweep index must be in 0..{RELABELLING_SWEEP_SIZE - 1}, got {index}"
        )
    stream = _keystream(f"routing-overhead|relabelling-sweep|{base}|{index:02d}")
    permutation = list(range(PHYSICAL_QUBITS))
    for position in range(PHYSICAL_QUBITS - 1, 0, -1):
        swap = _uniform_below(stream, position + 1)
        permutation[position], permutation[swap] = permutation[swap], permutation[position]
    return tuple(permutation)


def sweep_permutations_digest() -> str:
    """SHA-256 over every sweep permutation, in canonical order.

    A single value a test can pin. If any part of the derivation changes — the hash
    input, the shuffle, the rejection bound — this digest moves and the regression
    test fails, rather than the study silently running on different conditions.
    """
    payload = ";".join(
        f"{base}:{index:02d}:" + ",".join(str(q) for q in sweep_permutation(base, index))
        for base in SWEEP_BASES
        for index in range(RELABELLING_SWEEP_SIZE)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def identity_aligned_edges(name: str) -> int:
    """How many `(i, i+1)` pairs this map supports, i.e. how much of a chain
    `TrivialLayout` satisfies for free.

    This is the quantity the label-permutation control neutralises: 26 for the
    identity-labelled line, 0 for either relabelled map.
    """
    edges = set(undirected_edges(build_coupling_map(name)))
    return sum(1 for index in range(PHYSICAL_QUBITS - 1) if (index, index + 1) in edges)


def undirected_edges(coupling_map: CouplingMap) -> list[tuple[int, int]]:
    """Sorted, deduplicated undirected edge list — the canonical topology record."""
    return sorted({tuple(sorted(edge)) for edge in coupling_map.get_edges()})


def topology_hash(coupling_map: CouplingMap) -> str:
    """SHA-256 over the canonical undirected edge list."""
    payload = ";".join(f"{a}-{b}" for a, b in undirected_edges(coupling_map))
    return hashlib.sha256(f"{coupling_map.size()}|{payload}".encode()).hexdigest()


def topology_metadata(name: str) -> dict:
    """Descriptive record saved with every run."""
    coupling_map = build_coupling_map(name)
    edges = undirected_edges(coupling_map)
    graph = nx.Graph()
    graph.add_nodes_from(range(coupling_map.size()))
    graph.add_edges_from(edges)
    degrees = [degree for _, degree in graph.degree()]
    connected = nx.is_connected(graph)
    return {
        "topology": name,
        "base_topology": base_topology(name),
        "relabelled": is_relabelled(name),
        "physical_qubits": coupling_map.size(),
        "directed_edges": len(coupling_map.get_edges()),
        "undirected_edges": len(edges),
        "min_degree": min(degrees),
        "max_degree": max(degrees),
        "mean_degree": sum(degrees) / len(degrees),
        "diameter": nx.diameter(graph) if connected else None,
        "average_shortest_path_length": (
            nx.average_shortest_path_length(graph) if connected else None
        ),
        "connected": connected,
        # Not a graph property: how much of an (i, i+1)-indexed chain the identity
        # layout satisfies. Recorded so a run's own metadata shows whether its
        # topologies were index-aligned with the circuit builders.
        "identity_aligned_edges": sum(
            1 for index in range(coupling_map.size() - 1) if (index, index + 1) in set(edges)
        ),
        "edge_list_hash": topology_hash(coupling_map),
    }


def _symmetrized(edges: tuple[tuple[int, int], ...]) -> CouplingMap:
    """Build a bidirectional map from an undirected edge list.

    The controlled experiment studies undirected connectivity constraints, not
    calibrated directional gate support, so both directions are always present.
    """
    directed = [[a, b] for a, b in edges] + [[b, a] for a, b in edges]
    coupling_map = CouplingMap(couplinglist=directed)
    if coupling_map.size() != PHYSICAL_QUBITS:
        raise ValueError(f"expected {PHYSICAL_QUBITS} physical qubits, got {coupling_map.size()}")
    return coupling_map


@functools.lru_cache(maxsize=1)
def _cairo_undirected_edges() -> tuple[tuple[int, int], ...]:
    """Heavy-hex edges from the shipped FakeCairo device configuration snapshot.

    `FakeCairoV2().target` is NOT used as the source: its per-gate calibration
    lists drop two couplings — (0, 1) and (7, 10) — which leaves qubit 0 isolated
    and the graph disconnected. The backend configuration is the authoritative
    record of the device's connectivity, and it carries the full 28-edge graph.
    An immutable edge tuple is cached; the `CouplingMap` itself is rebuilt per call.
    """
    from qiskit_ibm_runtime.fake_provider import FakeCairoV2

    configuration = FakeCairoV2().configuration()
    return tuple(sorted({tuple(sorted(edge)) for edge in configuration.coupling_map}))
