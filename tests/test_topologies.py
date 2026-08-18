"""Stage 1 tests for the three controlled 27-qubit connectivity models."""

import itertools

import pytest

from routing_overhead.topologies import (
    PHYSICAL_QUBITS,
    TOPOLOGIES,
    build_coupling_map,
    topology_hash,
    topology_metadata,
)

# --- Cairo heavy-hex expectation -------------------------------------------------
# Isolated on purpose: this is the one topology whose source graph is under review.
CAIRO_UNDIRECTED_EDGES = 28
CAIRO_DIAMETER = 12
# ---------------------------------------------------------------------------------


@pytest.mark.parametrize("name", TOPOLOGIES)
def test_every_topology_has_27_physical_qubits(name):
    assert build_coupling_map(name).size() == PHYSICAL_QUBITS == 27


@pytest.mark.parametrize("name", TOPOLOGIES)
def test_every_topology_is_bidirectional(name):
    edges = set(build_coupling_map(name).get_edges())
    assert edges
    assert all((target, source) in edges for source, target in edges)


@pytest.mark.parametrize("name", TOPOLOGIES)
def test_every_topology_is_connected(name):
    assert topology_metadata(name)["connected"] is True


@pytest.mark.parametrize("name", TOPOLOGIES)
def test_no_topology_object_is_shared_between_calls(name):
    first = build_coupling_map(name)
    second = build_coupling_map(name)
    assert first is not second
    first.add_edge(26, 0)
    assert set(build_coupling_map(name).get_edges()) == set(second.get_edges())


def test_complete_map_has_distance_one_between_distinct_qubits():
    coupling_map = build_coupling_map("complete_27")
    assert all(
        coupling_map.distance(a, b) == 1
        for a, b in itertools.permutations(range(PHYSICAL_QUBITS), 2)
    )
    assert topology_metadata("complete_27")["undirected_edges"] == 27 * 26 // 2


def test_line_map_has_diameter_26():
    metadata = topology_metadata("line_27")
    assert metadata["diameter"] == 26
    assert metadata["undirected_edges"] == 26
    assert metadata["min_degree"] == 1
    assert metadata["max_degree"] == 2


def test_cairo_map_is_the_full_heavy_hex_graph():
    metadata = topology_metadata("cairo_heavy_hex_27")
    assert metadata["undirected_edges"] == CAIRO_UNDIRECTED_EDGES
    assert metadata["diameter"] == CAIRO_DIAMETER
    assert metadata["connected"] is True
    assert metadata["max_degree"] == 3


@pytest.mark.parametrize("name", TOPOLOGIES)
def test_metadata_reports_the_full_descriptive_record(name):
    metadata = topology_metadata(name)
    assert set(metadata) == {
        "topology",
        "base_topology",
        "relabelled",
        "physical_qubits",
        "directed_edges",
        "undirected_edges",
        "min_degree",
        "max_degree",
        "mean_degree",
        "diameter",
        "average_shortest_path_length",
        "connected",
        "identity_aligned_edges",
        "edge_list_hash",
    }
    assert metadata["topology"] == name
    assert metadata["physical_qubits"] == PHYSICAL_QUBITS
    assert metadata["directed_edges"] == 2 * metadata["undirected_edges"]
    assert metadata["edge_list_hash"] == topology_hash(build_coupling_map(name))


@pytest.mark.parametrize("name", TOPOLOGIES)
def test_topology_hash_is_stable_across_rebuilds(name):
    assert topology_hash(build_coupling_map(name)) == topology_hash(build_coupling_map(name))


def test_topology_hashes_are_distinct():
    assert len({topology_hash(build_coupling_map(name)) for name in TOPOLOGIES}) == len(TOPOLOGIES)


def test_unknown_topology_is_rejected():
    with pytest.raises(ValueError, match="unknown topology"):
        build_coupling_map("ring_27")
