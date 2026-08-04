"""Stage 2 tests for the minimum required figure."""

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from routing_overhead.aggregation import aggregate_run
from routing_overhead.config import ExperimentConfig
from routing_overhead.experiments import prepare_run_directory, run_grid
from routing_overhead.plotting import plot_run

CONFIG = ExperimentConfig(
    physical_qubits=27,
    logical_qubits=(4, 6),
    circuit_families=("ghz_star",),
    topologies=("complete_27", "line_27"),
    optimization_levels=(1,),
    transpiler_seeds=(11, 22),
    basis_gates=("rz", "sx", "x", "cx"),
)


@pytest.fixture(scope="module")
def aggregated_run(tmp_path_factory):
    run_dir = prepare_run_directory(CONFIG, tmp_path_factory.mktemp("runs"), "run-a")
    run_grid(CONFIG, run_dir)
    aggregate_run(run_dir)
    return run_dir


def test_plot_run_writes_the_two_qubit_depth_penalty_figure(aggregated_run):
    figures = plot_run(aggregated_run)

    assert figures
    for path in figures:
        assert path.is_file()
        assert path.stat().st_size > 0
    suffixes = {path.suffix for path in figures}
    assert suffixes == {".png", ".svg"}
    assert all(path.parent == aggregated_run / "figures" for path in figures)


def test_figure_is_generated_from_saved_summary_data(aggregated_run):
    summary = pd.read_parquet(aggregated_run / "summary_results.parquet")
    penalties = summary[summary["metric"] == "two_qubit_depth_penalty"]
    assert set(penalties["topology"]) == {"complete_27", "line_27"}
    assert penalties["count"].max() == 2


def _core_shaped_summary(run_dir, levels=(0, 1, 3), sizes=(4, 8)):
    records = [
        {
            "circuit_family": "ghz_star",
            "logical_qubits": size,
            "topology": topology,
            "optimization_level": level,
            "metric": "two_qubit_depth_penalty",
            "count": 2,
            "median": 1.0 + level,
            "q25": 1.0,
            "q75": 2.0,
            "iqr": 1.0,
            "min": 1.0,
            "max": 2.0,
            "mean": 1.5,
            "std": 0.1,
        }
        for level in levels
        for topology in ("complete_27", "line_27")
        for size in sizes
    ]
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_parquet(run_dir / "summary_results.parquet", index=False)
    return run_dir


def test_core_shaped_data_draws_one_series_per_constrained_topology_and_level(
    tmp_path, monkeypatch
):
    run_dir = _core_shaped_summary(tmp_path / "core")
    calls = []
    real_plot = plt.Axes.plot

    def record(self, *args, **kwargs):
        calls.append((list(args[0]), kwargs.get("label")))
        return real_plot(self, *args, **kwargs)

    monkeypatch.setattr(plt.Axes, "plot", record)
    plot_run(run_dir)

    # Three levels for line_27 only: complete_27 is the ratio's denominator and is
    # drawn once as a baseline line rather than as three flat series.
    assert len(calls) == 3, calls
    for xs, _ in calls:
        assert xs == [4, 8], xs
    labels = [label for _, label in calls]
    assert len(set(labels)) == 3
    assert not any("Complete" in label for label in labels)
    assert all("L0" in label or "L1" in label or "L3" in label for label in labels)


def test_single_level_data_still_draws_the_constrained_series(tmp_path, monkeypatch):
    run_dir = _core_shaped_summary(tmp_path / "smoke-shaped", levels=(1,))
    calls = []
    real_plot = plt.Axes.plot
    monkeypatch.setattr(
        plt.Axes,
        "plot",
        lambda self, *a, **k: (calls.append(list(a[0])), real_plot(self, *a, **k))[1],
    )
    plot_run(run_dir)

    assert len(calls) == 1
    assert all(xs == [4, 8] for xs in calls)


def test_plot_run_requires_aggregation_first(tmp_path):
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-b")
    with pytest.raises(FileNotFoundError, match="summary_results.parquet"):
        plot_run(run_dir)
