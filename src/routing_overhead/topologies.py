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

TOPOLOGIES = ("complete_27", "line_27", "cairo_heavy_hex_27")


def build_coupling_map(name: str) -> CouplingMap:
    """Return a fresh, bidirectional `CouplingMap` for `name`.

    A new object is built on every call so runs can never mutate a shared map.
    """
    if name not in TOPOLOGIES:
        raise ValueError(f"unknown topology: {name!r}; expected one of {TOPOLOGIES}")
    if name == "complete_27":
        return CouplingMap.from_full(PHYSICAL_QUBITS, bidirectional=True)
    if name == "line_27":
        return CouplingMap.from_line(PHYSICAL_QUBITS, bidirectional=True)
    return _symmetrized(_cairo_undirected_edges())


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
