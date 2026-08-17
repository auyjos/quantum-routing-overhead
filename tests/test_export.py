"""Tests for the JSON export of a run's summary, raw results, and topologies."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from routing_overhead.aggregation import aggregate_run
from routing_overhead.config import ExperimentConfig
from routing_overhead.experiments import prepare_run_directory, run_grid
from routing_overhead.export import export_run


def _aggregated_run(tmp_path: Path) -> Path:
    config = ExperimentConfig(
        physical_qubits=27,
        logical_qubits=(4,),
        circuit_families=("ghz_star",),
        topologies=("complete_27", "line_27"),
        optimization_levels=(1,),
        transpiler_seeds=(11,),
        basis_gates=("rz", "sx", "x", "cx"),
    )
    run_dir = prepare_run_directory(config, tmp_path, "run-a")
    run_grid(config, run_dir)
    aggregate_run(run_dir)
    return run_dir


def test_export_run_writes_a_json_file_with_the_documented_top_level_keys(tmp_path):
    run_dir = _aggregated_run(tmp_path)

    result = export_run(run_dir)

    path = run_dir / "export" / "results.json"
    assert result["path"] == path
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == {"provenance", "topologies", "summary", "raw"}


def test_export_run_provenance_matches_the_run_environment(tmp_path):
    run_dir = _aggregated_run(tmp_path)

    export_run(run_dir)

    payload = json.loads((run_dir / "export" / "results.json").read_text(encoding="utf-8"))
    provenance = payload["provenance"]
    assert provenance["run_id"] == "run-a"
    assert provenance["qiskit_version"]
    assert provenance["config"]["circuit_families"] == ["ghz_star"]


def test_export_run_topologies_include_graph_statistics(tmp_path):
    run_dir = _aggregated_run(tmp_path)

    export_run(run_dir)

    payload = json.loads((run_dir / "export" / "results.json").read_text(encoding="utf-8"))
    by_name = {row["topology"]: row for row in payload["topologies"]}
    assert set(by_name) == {"complete_27", "line_27"}
    assert by_name["line_27"]["diameter"] == 26
    assert by_name["line_27"]["undirected_edges"] == 26


def test_export_run_summary_and_raw_rows_match_the_aggregated_tables(tmp_path):
    run_dir = _aggregated_run(tmp_path)

    result = export_run(run_dir)

    payload = json.loads((run_dir / "export" / "results.json").read_text(encoding="utf-8"))
    assert len(payload["summary"]) == result["summary_rows"] > 0
    assert len(payload["raw"]) == result["raw_rows"] == 2
    raw_row = payload["raw"][0]
    assert {"circuit_family", "topology", "two_qubit_depth_penalty", "success"} <= set(raw_row)


def test_export_run_writes_null_not_nan_for_missing_values(tmp_path):
    run_dir = _aggregated_run(tmp_path)

    export_run(run_dir)

    text = (run_dir / "export" / "results.json").read_text(encoding="utf-8")
    # Python's json module accepts the non-standard NaN/Infinity tokens on read; a
    # strict decoder elsewhere would not, so the file must never contain them.
    assert "NaN" not in text
    assert "Infinity" not in text
    payload = json.loads(text)
    baseline_row = next(row for row in payload["raw"] if row["topology"] == "complete_27")
    assert baseline_row["depth_penalty"] == pytest.approx(1.0)


def test_export_run_raises_when_the_run_has_not_been_aggregated(tmp_path):
    config = ExperimentConfig(
        physical_qubits=27,
        logical_qubits=(4,),
        circuit_families=("ghz_star",),
        topologies=("complete_27",),
        optimization_levels=(1,),
        transpiler_seeds=(11,),
        basis_gates=("rz", "sx", "x", "cx"),
    )
    run_dir = prepare_run_directory(config, tmp_path, "run-a")
    run_grid(config, run_dir)

    with pytest.raises(FileNotFoundError, match="aggregate"):
        export_run(run_dir)
