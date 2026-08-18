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

RELABELLED_BASES = {
    "line_27" + RELABELLED_SUFFIX: "line_27",
    "cairo_heavy_hex_27" + RELABELLED_SUFFIX: "cairo_heavy_hex_27",
}

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

TOPOLOGIES = (*BASE_TOPOLOGIES, *RELABELLED_BASES)


def base_topology(name: str) -> str:
    """The graph a topology is built from: itself, or the base a control relabels."""
    return RELABELLED_BASES.get(name, name)


def is_relabelled(name: str) -> bool:
    """True for the label-permutation controls."""
    return name in RELABELLED_BASES


def build_coupling_map(name: str) -> CouplingMap:
    """Return a fresh, bidirectional `CouplingMap` for `name`.

    A new object is built on every call so runs can never mutate a shared map.
    """
    if name not in TOPOLOGIES:
        raise ValueError(f"unknown topology: {name!r}; expected one of {TOPOLOGIES}")
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
    permutation = PERMUTATIONS[base]
    edges = undirected_edges(build_coupling_map(base))
    return tuple(sorted({tuple(sorted((permutation[a], permutation[b]))) for a, b in edges}))


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
