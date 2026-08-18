"""Stage 2 tests for baseline joins, penalty ratios and summary statistics."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from routing_overhead.aggregation import (
    BASELINE_TOPOLOGY,
    add_penalties,
    aggregate_run,
    penalty_warnings,
    summarize,
)
from routing_overhead.config import ExperimentConfig
from routing_overhead.experiments import (
    completed_experiment_ids,
    prepare_run_directory,
    read_raw_results,
    run_grid,
)

BASE_ROW = {
    "circuit_family": "ghz_star",
    "logical_qubits": 4,
    "circuit_hash": "hash-a",
    "optimization_level": 1,
    "transpiler_seed": 11,
    "basis_gates": "cx,rz,sx,x",
    "output_depth": 6,
    "output_two_qubit_depth": 3,
    "output_two_qubit_count": 3,
    "success": True,
}


def frame(*rows):
    return pd.DataFrame([{**BASE_ROW, **row} for row in rows])


def test_constrained_row_is_divided_by_its_complete_baseline():
    result = add_penalties(
        frame(
            {"topology": BASELINE_TOPOLOGY},
            {
                "topology": "line_27",
                "output_depth": 12,
                "output_two_qubit_depth": 6,
                "output_two_qubit_count": 9,
            },
        )
    )
    line = result[result["topology"] == "line_27"].iloc[0]
    assert line["depth_penalty"] == pytest.approx(2.0)
    assert line["two_qubit_depth_penalty"] == pytest.approx(2.0)
    assert line["two_qubit_count_penalty"] == pytest.approx(3.0)


def test_baseline_row_has_unit_penalties():
    result = add_penalties(frame({"topology": BASELINE_TOPOLOGY}))
    assert result.loc[0, "two_qubit_depth_penalty"] == pytest.approx(1.0)


def test_join_uses_the_baseline_of_the_matching_seed():
    result = add_penalties(
        frame(
            {"topology": BASELINE_TOPOLOGY, "transpiler_seed": 11, "output_two_qubit_depth": 3},
            {"topology": BASELINE_TOPOLOGY, "transpiler_seed": 22, "output_two_qubit_depth": 6},
            {"topology": "line_27", "transpiler_seed": 22, "output_two_qubit_depth": 12},
        )
    )
    line = result[result["topology"] == "line_27"].iloc[0]
    assert line["two_qubit_depth_penalty"] == pytest.approx(2.0)


def test_join_requires_a_matching_circuit_hash():
    result = add_penalties(
        frame(
            {"topology": BASELINE_TOPOLOGY, "circuit_hash": "hash-a"},
            {"topology": "line_27", "circuit_hash": "hash-b", "output_two_qubit_depth": 12},
        )
    )
    line = result[result["topology"] == "line_27"].iloc[0]
    assert pd.isna(line["two_qubit_depth_penalty"])
    assert any("no complete baseline" in warning for warning in penalty_warnings(result))


def test_zero_over_zero_is_not_applicable_and_is_not_a_warning():
    result = add_penalties(
        frame(
            {"topology": BASELINE_TOPOLOGY, "output_two_qubit_depth": 0},
            {"topology": "line_27", "output_two_qubit_depth": 0},
        )
    )
    assert result["two_qubit_depth_penalty"].isna().all()
    assert not any("zero baseline" in warning for warning in penalty_warnings(result))


def test_zero_baseline_with_nonzero_numerator_is_flagged():
    result = add_penalties(
        frame(
            {"topology": BASELINE_TOPOLOGY, "output_two_qubit_depth": 0},
            {"topology": "line_27", "output_two_qubit_depth": 4},
        )
    )
    line = result[result["topology"] == "line_27"].iloc[0]
    assert pd.isna(line["two_qubit_depth_penalty"])
    assert any("zero baseline" in warning for warning in penalty_warnings(result))


def test_failed_runs_get_no_penalties():
    result = add_penalties(
        frame(
            {"topology": BASELINE_TOPOLOGY},
            {
                "topology": "line_27",
                "success": False,
                "output_depth": None,
                "output_two_qubit_depth": None,
                "output_two_qubit_count": None,
            },
        )
    )
    line = result[result["topology"] == "line_27"].iloc[0]
    assert pd.isna(line["two_qubit_depth_penalty"])


def test_duplicate_baselines_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        add_penalties(
            frame(
                {"topology": BASELINE_TOPOLOGY},
                {"topology": BASELINE_TOPOLOGY},
            )
        )


def test_summary_reports_the_planned_statistics():
    result = add_penalties(
        frame(
            {"topology": BASELINE_TOPOLOGY, "transpiler_seed": 11, "output_two_qubit_depth": 3},
            {"topology": BASELINE_TOPOLOGY, "transpiler_seed": 22, "output_two_qubit_depth": 3},
            {"topology": "line_27", "transpiler_seed": 11, "output_two_qubit_depth": 3},
            {"topology": "line_27", "transpiler_seed": 22, "output_two_qubit_depth": 6},
        )
    )
    summary = summarize(result)
    row = summary[
        (summary["topology"] == "line_27") & (summary["metric"] == "two_qubit_depth_penalty")
    ].iloc[0]
    assert row["count"] == 2
    assert row["median"] == pytest.approx(1.5)
    assert row["iqr"] == pytest.approx(0.5)
    assert row["min"] == pytest.approx(1.0)
    assert row["max"] == pytest.approx(2.0)
    assert row["mean"] == pytest.approx(1.5)
    assert row["std"] == pytest.approx(np.std([1.0, 2.0], ddof=1))
    assert set(summary["metric"]) >= {
        "depth_penalty",
        "two_qubit_depth_penalty",
        "two_qubit_count_penalty",
    }


def test_single_observation_reports_undefined_standard_deviation():
    result = add_penalties(
        frame(
            {"topology": BASELINE_TOPOLOGY, "transpiler_seed": 11, "output_two_qubit_depth": 3},
            {"topology": "line_27", "transpiler_seed": 11, "output_two_qubit_depth": 6},
        )
    )
    row = summarize(result)
    row = row[(row["topology"] == "line_27") & (row["metric"] == "two_qubit_depth_penalty")].iloc[0]
    assert row["count"] == 1
    assert row["median"] == pytest.approx(2.0)
    assert pd.isna(row["std"])


def test_interrupted_aggregation_leaves_the_previous_journal_readable(tmp_path, monkeypatch):
    run_dir = _completed_run(tmp_path)
    aggregate_run(run_dir)
    before = read_raw_results(run_dir)

    def truncating_to_csv(self, path_or_buf=None, **kwargs):
        Path(path_or_buf).write_text("partial", encoding="utf-8")
        raise RuntimeError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_csv", truncating_to_csv)
    with pytest.raises(RuntimeError, match="disk full"):
        aggregate_run(run_dir)

    assert completed_experiment_ids(run_dir) == set(before["experiment_id"])
    pd.testing.assert_frame_equal(read_raw_results(run_dir), before)


def test_interrupted_parquet_write_leaves_the_previous_table_readable(tmp_path, monkeypatch):
    run_dir = _completed_run(tmp_path)
    aggregate_run(run_dir)
    before = pd.read_parquet(run_dir / "raw_results.parquet")

    def truncating_to_parquet(self, path=None, **kwargs):
        Path(path).write_bytes(b"not parquet")
        raise RuntimeError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", truncating_to_parquet)
    with pytest.raises(RuntimeError, match="disk full"):
        aggregate_run(run_dir)

    pd.testing.assert_frame_equal(pd.read_parquet(run_dir / "raw_results.parquet"), before)


def test_aggregation_leaves_no_temporary_files_behind(tmp_path):
    run_dir = _completed_run(tmp_path)
    aggregate_run(run_dir)
    assert not list(run_dir.glob("*.tmp"))


def _completed_run(tmp_path):
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
    return run_dir


def test_aggregate_run_fills_raw_penalties_and_writes_the_summary(tmp_path):
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

    raw = pd.read_parquet(run_dir / "raw_results.parquet")
    assert len(raw) == 2
    assert raw["two_qubit_depth_penalty"].notna().all()
    line = raw[raw["topology"] == "line_27"].iloc[0]
    assert line["two_qubit_depth_penalty"] > 1.0

    summary = pd.read_parquet(run_dir / "summary_results.parquet")
    assert set(summary.columns) == {
        "circuit_family",
        "logical_qubits",
        "topology",
        "optimization_level",
        "metric",
        "count",
        "median",
        "q25",
        "q75",
        "iqr",
        "min",
        "max",
        "mean",
        "geometric_mean",
        "std",
    }
    assert len(summary) > 0
    assert pd.read_csv(run_dir / "raw_results.csv")["two_qubit_depth_penalty"].notna().all()
