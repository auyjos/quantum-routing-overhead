"""End-to-end smoke grid: the documented 16-run gate for the experiment engine."""

import json
from pathlib import Path

import pandas as pd
import pytest

from routing_overhead.aggregation import aggregate_run
from routing_overhead.config import load_config
from routing_overhead.experiments import prepare_run_directory, run_grid
from routing_overhead.plotting import plot_run

SMOKE_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "smoke.yaml"


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory):
    config = load_config(SMOKE_CONFIG)
    run_dir = prepare_run_directory(config, tmp_path_factory.mktemp("runs"), "smoke")
    counts = run_grid(config, run_dir)
    return config, run_dir, counts


def test_smoke_grid_is_sixteen_runs(smoke_run):
    config, _, counts = smoke_run
    assert config.size() == 16
    assert counts == {"planned": 16, "executed": 16, "skipped": 0, "failed": 0}


def test_all_expected_rows_exist_without_duplicates(smoke_run):
    _, run_dir, _ = smoke_run
    raw = pd.read_parquet(run_dir / "raw_results.parquet")
    assert len(raw) == 16
    assert raw["experiment_id"].nunique() == 16
    assert raw["planned_point_id"].nunique() == 16
    assert raw["success"].all()
    assert not raw.duplicated(
        subset=[
            "circuit_family",
            "logical_qubits",
            "topology",
            "optimization_level",
            "transpiler_seed",
        ]
    ).any()


def test_identical_circuits_reach_every_topology(smoke_run):
    _, run_dir, _ = smoke_run
    raw = pd.read_parquet(run_dir / "raw_results.parquet")
    per_circuit = raw.groupby(["circuit_family", "logical_qubits"])["circuit_hash"].nunique()
    assert (per_circuit == 1).all()


def test_raw_results_save_in_both_formats(smoke_run):
    _, run_dir, _ = smoke_run
    assert len(pd.read_csv(run_dir / "raw_results.csv")) == 16
    assert len(pd.read_parquet(run_dir / "raw_results.parquet")) == 16
    assert not (run_dir / "failures.csv").exists()


def test_environment_and_topology_metadata_exist(smoke_run):
    _, run_dir, _ = smoke_run
    environment = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
    assert environment["worker_count"] == 1
    assert environment["packages"]["qiskit"]
    assert environment["config"]["transpiler_seeds"] == [11, 22]
    assert environment["rows"] == 16

    topologies = pd.read_parquet(run_dir / "topology_metadata.parquet")
    assert set(topologies["topology"]) == {"complete_27", "line_27"}
    assert topologies["connected"].all()
    circuits = pd.read_parquet(run_dir / "circuit_metadata.parquet")
    assert len(circuits) == 4


def test_aggregation_and_plotting_succeed(smoke_run):
    _, run_dir, _ = smoke_run
    result = aggregate_run(run_dir)
    assert result["rows"] == 16
    assert result["warnings"] == []

    raw = pd.read_parquet(run_dir / "raw_results.parquet")
    assert raw["two_qubit_depth_penalty"].notna().all()
    baseline = raw[raw["topology"] == "complete_27"]
    assert (baseline["two_qubit_depth_penalty"] == 1.0).all()

    figures = plot_run(run_dir)
    assert figures
    assert all(path.is_file() for path in figures)


def test_line_connectivity_shows_routing_overhead_on_the_star(smoke_run):
    _, run_dir, _ = smoke_run
    aggregate_run(run_dir)
    raw = pd.read_parquet(run_dir / "raw_results.parquet")
    star_line = raw[(raw["circuit_family"] == "ghz_star") & (raw["topology"] == "line_27")]
    assert (star_line["two_qubit_count_penalty"] > 1.0).all()
