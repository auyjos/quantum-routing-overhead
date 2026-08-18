"""Label-permutation control: the relabelled maps and the invariance report."""

import networkx as nx
import pandas as pd
import pytest

from routing_overhead.aggregation import GROUP_KEYS, geometric_mean, pooled_summary
from routing_overhead.controls import (
    available_controls,
    classify,
    control_run,
    invariance_by_level,
    label_invariance,
)
from routing_overhead.topologies import (
    PERMUTATIONS,
    PHYSICAL_QUBITS,
    RELABELLED_BASES,
    base_topology,
    build_coupling_map,
    identity_aligned_edges,
    is_relabelled,
    topology_hash,
    topology_metadata,
    undirected_edges,
)

CONTROL_PAIRS = sorted(RELABELLED_BASES.items())


def _graph(name):
    graph = nx.Graph()
    graph.add_nodes_from(range(PHYSICAL_QUBITS))
    graph.add_edges_from(undirected_edges(build_coupling_map(name)))
    return graph


@pytest.mark.parametrize("base", sorted(PERMUTATIONS))
def test_each_permutation_is_a_derangement_of_the_physical_qubits(base):
    """A fixed point would leave part of the original labelling in place."""
    permutation = PERMUTATIONS[base]
    assert sorted(permutation) == list(range(PHYSICAL_QUBITS))
    assert all(permutation[index] != index for index in range(PHYSICAL_QUBITS))


@pytest.mark.parametrize(("control", "base"), CONTROL_PAIRS)
def test_the_control_is_the_same_graph_as_its_base(control, base):
    """The control may differ only in labelling: isomorphism is the whole premise."""
    assert nx.is_isomorphic(_graph(control), _graph(base))


@pytest.mark.parametrize(("control", "base"), CONTROL_PAIRS)
def test_every_reported_connectivity_property_is_identical(control, base):
    """If any of these moved, a base/control difference would not isolate labelling."""
    shared = (
        "physical_qubits",
        "directed_edges",
        "undirected_edges",
        "min_degree",
        "max_degree",
        "mean_degree",
        "diameter",
        "average_shortest_path_length",
        "connected",
    )
    control_metadata = topology_metadata(control)
    base_metadata = topology_metadata(base)
    for key in shared:
        assert control_metadata[key] == base_metadata[key], key


@pytest.mark.parametrize(("control", "base"), CONTROL_PAIRS)
def test_the_control_removes_every_identity_aligned_chain_edge(control, base):
    """The confound under test: how much of an (i, i+1) chain the identity layout gets free."""
    assert identity_aligned_edges(base) > 0
    assert identity_aligned_edges(control) == 0


@pytest.mark.parametrize(("control", "base"), CONTROL_PAIRS)
def test_the_control_is_a_distinct_recorded_topology(control, base):
    """Same graph, different labelling: the stored edge-list hash must not collide."""
    assert topology_hash(build_coupling_map(control)) != topology_hash(build_coupling_map(base))
    assert is_relabelled(control)
    assert not is_relabelled(base)
    assert base_topology(control) == base
    assert base_topology(base) == base
    assert topology_metadata(control)["relabelled"] is True


def test_the_line_control_is_still_a_path_and_cairo_is_still_heavy_hex():
    """Relabelling must not quietly produce a different family of graph."""
    line = _graph("line_27_relabelled")
    assert sorted(degree for _, degree in line.degree()) == [1, 1] + [2] * 25
    cairo = _graph("cairo_heavy_hex_27_relabelled")
    assert sorted(len(cycle) for cycle in nx.simple_cycles(cairo)) == sorted(
        len(cycle) for cycle in nx.simple_cycles(_graph("cairo_heavy_hex_27"))
    )


def test_the_structural_embedding_sizes_survive_relabelling():
    """The reported {12, 20} cycle lengths and 21-node longest path are graph facts.

    They are what makes Efficient SU(2) land at exactly 1.000x at n=12 and n=20 and
    forbids a 24-qubit chain embedding, so the control must preserve them exactly.
    """
    for name in ("cairo_heavy_hex_27", "cairo_heavy_hex_27_relabelled"):
        graph = _graph(name)
        assert {len(cycle) for cycle in nx.simple_cycles(graph)} == {12, 20}
        assert _longest_simple_path(graph) == 21


def _longest_simple_path(graph) -> int:
    """Exhaustive depth-first search over simple paths; the graph has 27 nodes."""
    best = 0

    def walk(node, visited):
        nonlocal best
        best = max(best, len(visited))
        for neighbour in graph[node]:
            if neighbour not in visited:
                visited.add(neighbour)
                walk(neighbour, visited)
                visited.remove(neighbour)

    for start in graph.nodes():
        walk(start, {start})
    return best


def _frame(rows):
    records = []
    for family, qubits, topology, level, seed, penalty in rows:
        records.append(
            {
                "circuit_family": family,
                "logical_qubits": qubits,
                "topology": topology,
                "optimization_level": level,
                "transpiler_seed": seed,
                "two_qubit_depth_penalty": penalty,
                "success": True,
            }
        )
    return pd.DataFrame.from_records(records)


def test_label_invariance_flags_a_shift_and_clears_an_unchanged_level():
    frame = _frame(
        [
            # level 0: the control is far worse -> the base was riding on its labelling
            ("ghz_chain", 4, "line_27", 0, 11, 1.0),
            ("ghz_chain", 4, "line_27", 0, 22, 1.0),
            ("ghz_chain", 4, "line_27_relabelled", 0, 11, 9.0),
            ("ghz_chain", 4, "line_27_relabelled", 0, 22, 9.0),
            # level 3: unchanged -> label-invariant
            ("ghz_chain", 4, "line_27", 3, 11, 1.0),
            ("ghz_chain", 4, "line_27", 3, 22, 1.0),
            ("ghz_chain", 4, "line_27_relabelled", 3, 11, 1.0),
            ("ghz_chain", 4, "line_27_relabelled", 3, 22, 1.0),
        ]
    )
    report = label_invariance(frame)
    assert list(report["optimization_level"]) == [0, 3]
    sensitive, invariant = report.iloc[0], report.iloc[1]
    assert not bool(sensitive["label_invariant"])
    assert sensitive["relative_shift"] == pytest.approx(9.0)
    assert sensitive["seeds"] == 2
    assert bool(invariant["label_invariant"])
    assert invariant["relative_shift"] == pytest.approx(1.0)

    by_level = invariance_by_level(report)
    assert dict(zip(by_level["optimization_level"], by_level["invariant_fraction"])) == {
        0: 0.0,
        3: 1.0,
    }
    assert dict(zip(by_level["optimization_level"], by_level["verdict"])) == {
        0: "label-sensitive",
        3: "label-invariant",
    }


def test_disjoint_seed_ranges_are_reported_as_systematic():
    """The strong verdict: every seed moved the same way, so it cannot be scatter."""
    frame = _frame(
        [
            ("ghz_star", 20, "line_27", 3, 11, 1.9),
            ("ghz_star", 20, "line_27", 3, 22, 2.1),
            ("ghz_star", 20, "line_27_relabelled", 3, 11, 5.1),
            ("ghz_star", 20, "line_27_relabelled", 3, 22, 5.4),
        ]
    )
    row = label_invariance(frame).iloc[0]
    assert not bool(row["seed_ranges_overlap"])
    assert bool(row["systematic"])
    assert row["base_max"] == pytest.approx(2.1)
    assert row["relabelled_min"] == pytest.approx(5.1)


def test_overlapping_seed_ranges_are_not_called_systematic():
    """A shifted median inside shared scatter is seed noise, not a labelling effect."""
    frame = _frame(
        [
            ("qft", 20, "line_27", 3, 11, 2.0),
            ("qft", 20, "line_27", 3, 22, 3.0),
            ("qft", 20, "line_27_relabelled", 3, 11, 2.4),
            ("qft", 20, "line_27_relabelled", 3, 22, 2.9),
        ]
    )
    row = label_invariance(frame).iloc[0]
    assert bool(row["seed_ranges_overlap"])
    assert not bool(row["systematic"])
    assert not bool(row["label_invariant"])


def test_classify_separates_noise_from_a_labelling_effect():
    """Symmetric shifts within scatter are noise; a biased or disjoint shift is not."""
    noise = pd.DataFrame(
        {
            "label_invariant": [False, False],
            "systematic": [False, False],
            # Reciprocal pair: geometric mean is exactly 1, so there is no bias.
            "relative_shift": [0.8, 1.25],
        }
    )
    assert classify(noise) == "noise-only"

    biased = pd.DataFrame(
        {
            "label_invariant": [False, False],
            "systematic": [False, False],
            "relative_shift": [1.25, 1.30],
        }
    )
    assert classify(biased) == "label-sensitive"

    disjoint = pd.DataFrame(
        {"label_invariant": [False], "systematic": [True], "relative_shift": [1.001]}
    )
    assert classify(disjoint) == "label-sensitive"

    unchanged = pd.DataFrame(
        {"label_invariant": [True], "systematic": [False], "relative_shift": [1.0]}
    )
    assert classify(unchanged) == "label-invariant"


def test_label_invariance_ignores_failed_rows():
    frame = _frame(
        [
            ("qft", 4, "line_27", 3, 11, 2.0),
            ("qft", 4, "line_27_relabelled", 3, 11, 2.0),
            ("qft", 4, "line_27_relabelled", 3, 22, 99.0),
        ]
    )
    frame.loc[frame["transpiler_seed"] == 22, "success"] = False
    report = label_invariance(frame)
    assert len(report) == 1
    assert bool(report.iloc[0]["label_invariant"])


def test_label_invariance_is_empty_without_a_control():
    frame = _frame([("qft", 4, "line_27", 3, 11, 2.0)])
    assert label_invariance(frame).empty
    assert invariance_by_level(label_invariance(frame)).empty
    assert available_controls(frame) == []


def test_available_controls_requires_both_halves_of_the_pair():
    both = _frame(
        [
            ("qft", 4, "line_27", 3, 11, 2.0),
            ("qft", 4, "line_27_relabelled", 3, 11, 2.0),
        ]
    )
    assert available_controls(both) == ["line_27"]
    only_control = _frame([("qft", 4, "line_27_relabelled", 3, 11, 2.0)])
    assert available_controls(only_control) == []


def test_control_run_refuses_a_run_without_a_control(tmp_path, monkeypatch):
    frame = _frame([("qft", 4, "line_27", 3, 11, 2.0)])
    monkeypatch.setattr("routing_overhead.experiments.read_raw_results", lambda _: frame)
    with pytest.raises(ValueError, match="no label-permutation control"):
        control_run(tmp_path)


def test_control_run_writes_both_tables(tmp_path, monkeypatch):
    frame = _frame(
        [
            ("qft", 4, "line_27", 3, 11, 2.0),
            ("qft", 4, "line_27_relabelled", 3, 11, 2.0),
        ]
    )
    monkeypatch.setattr("routing_overhead.experiments.read_raw_results", lambda _: frame)
    result = control_run(tmp_path)
    assert result["controls"] == ["line_27"]
    assert result["clean_levels"] == [3]
    assert result["systematic"].empty
    assert (tmp_path / "label_invariance.csv").is_file()
    assert (tmp_path / "label_invariance_by_level.csv").is_file()


def test_geometric_mean_is_undefined_for_non_positive_values():
    assert geometric_mean([1.0, 4.0]) == pytest.approx(2.0)
    assert geometric_mean([2.0, 8.0]) == pytest.approx(4.0)
    assert pd.isna(geometric_mean([1.0, 0.0]))
    assert pd.isna(geometric_mean([]))


def test_geometric_mean_treats_reciprocal_ratios_symmetrically():
    """The property that makes it the right summary for normalized ratios."""
    assert geometric_mean([0.5, 2.0]) == pytest.approx(1.0)


def test_pooled_summary_separates_single_run_from_best_of_seeds():
    frame = _frame(
        [
            ("qft", 4, "line_27", 3, 11, 4.0),
            ("qft", 4, "line_27", 3, 22, 2.0),
            ("qft", 8, "line_27", 3, 11, 4.0),
            ("qft", 8, "line_27", 3, 22, 2.0),
        ]
    )
    pooled = pooled_summary(frame)
    assert list(pooled["topology"]) == ["line_27"]
    row = pooled.iloc[0]
    assert row["count"] == 4
    assert row["median"] == pytest.approx(3.0)
    assert row["geometric_mean"] == pytest.approx(8.0**0.5)
    # Two configurations, each best-of-two seeds -> both minima are 2.0.
    assert row["configurations"] == 2
    assert row["best_of_seeds_median"] == pytest.approx(2.0)
    assert row["best_of_seeds_geometric_mean"] == pytest.approx(2.0)


def test_pooled_summary_group_keys_match_the_summary_table():
    """Best-of-seeds must collapse exactly the seed axis and nothing else."""
    assert "transpiler_seed" not in GROUP_KEYS
    assert set(GROUP_KEYS) == {
        "circuit_family",
        "logical_qubits",
        "topology",
        "optimization_level",
    }
