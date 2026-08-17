"""Stage 2 tests for the required CLI commands."""

import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

from routing_overhead.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]

TINY = {
    "physical_qubits": 27,
    "logical_qubits": [4],
    "circuit_families": ["ghz_star"],
    "topologies": ["complete_27", "line_27"],
    "optimization_levels": [1],
    "transpiler_seeds": [11],
    "basis_gates": ["rz", "sx", "x", "cx"],
}


@pytest.fixture
def tiny_config(tmp_path):
    path = tmp_path / "tiny.yaml"
    path.write_text(yaml.safe_dump(TINY), encoding="utf-8")
    return path


def test_validate_config_accepts_the_shipped_smoke_grid(capsys):
    assert main(["validate-config", str(REPO_ROOT / "configs" / "smoke.yaml")]) == 0
    assert "16" in capsys.readouterr().out


def test_validate_config_exits_nonzero_on_an_invalid_file(tmp_path, capsys):
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump({**TINY, "topologies": ["ring_27"]}), encoding="utf-8")
    assert main(["validate-config", str(path)]) != 0
    assert "topologies" in capsys.readouterr().err


def test_validate_config_exits_nonzero_on_an_unhashable_axis_value(tmp_path, capsys):
    path = tmp_path / "nested.yaml"
    path.write_text(yaml.safe_dump({**TINY, "logical_qubits": [[4], [4]]}), encoding="utf-8")

    assert main(["validate-config", str(path)]) != 0

    error_output = capsys.readouterr().err
    assert "invalid configuration" in error_output
    assert "Traceback" not in error_output


def test_validate_config_exits_nonzero_on_a_missing_file(tmp_path):
    assert main(["validate-config", str(tmp_path / "absent.yaml")]) != 0


def test_run_creates_a_run_directory_and_prints_it(tmp_path, tiny_config, capsys):
    exit_code = main(
        ["run", "--config", str(tiny_config), "--artifacts", str(tmp_path), "--run-id", "r1"]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    run_dir = tmp_path / "r1"
    assert str(run_dir) in output
    assert (run_dir / "raw_results.parquet").is_file()
    assert len(pd.read_parquet(run_dir / "raw_results.parquet")) == 2


def test_run_refuses_to_overwrite_an_existing_run_directory(tmp_path, tiny_config, capsys):
    argv = ["run", "--config", str(tiny_config), "--artifacts", str(tmp_path), "--run-id", "r1"]
    assert main(argv) == 0
    assert main(argv) != 0
    assert "already exists" in capsys.readouterr().err


def test_run_resumes_without_duplicates(tmp_path, tiny_config, capsys):
    argv = ["run", "--config", str(tiny_config), "--artifacts", str(tmp_path), "--run-id", "r1"]
    assert main(argv) == 0
    assert main([*argv, "--resume"]) == 0
    assert "skipped=2" in capsys.readouterr().out

    raw = pd.read_parquet(tmp_path / "r1" / "raw_results.parquet")
    assert len(raw) == 2
    assert raw["experiment_id"].nunique() == 2


def test_aggregate_and_plot_complete_the_pipeline(tmp_path, tiny_config, capsys):
    main(["run", "--config", str(tiny_config), "--artifacts", str(tmp_path), "--run-id", "r1"])
    run_dir = tmp_path / "r1"

    assert main(["aggregate", "--run", str(run_dir)]) == 0
    assert (run_dir / "summary_results.parquet").is_file()

    assert main(["plot", "--run", str(run_dir)]) == 0
    assert list((run_dir / "figures").glob("*.png"))
    assert str(run_dir) in capsys.readouterr().out


def test_plot_accepts_repeat_timing_runs_and_rejects_mismatched_ones(tmp_path, tiny_config, capsys):
    main(["run", "--config", str(tiny_config), "--artifacts", str(tmp_path), "--run-id", "r1"])
    run_dir = tmp_path / "r1"
    main(["aggregate", "--run", str(run_dir)])
    repeat = tmp_path / "r2"
    shutil.copytree(run_dir, repeat)

    assert main(["plot", "--run", str(run_dir), "--timing-run", str(repeat)]) == 0
    assert (run_dir / "figures" / "optimization_quality_vs_time.png").is_file()

    frame = pd.read_csv(repeat / "raw_results.csv")
    frame.loc[0, "output_two_qubit_depth"] += 1
    frame.to_csv(repeat / "raw_results.csv", index=False, na_rep="")

    assert main(["plot", "--run", str(run_dir), "--timing-run", str(repeat)]) != 0
    assert "does not reproduce" in capsys.readouterr().err


def test_plot_reads_a_run_collected_before_planned_point_id(tmp_path, tiny_config, capsys):
    main(["run", "--config", str(tiny_config), "--artifacts", str(tmp_path), "--run-id", "r1"])
    run_dir = tmp_path / "r1"
    main(["aggregate", "--run", str(run_dir)])
    legacy = tmp_path / "legacy"
    shutil.copytree(run_dir, legacy)
    frame = pd.read_csv(legacy / "raw_results.csv")
    frame.drop(columns=["planned_point_id"]).to_csv(
        legacy / "raw_results.csv", index=False, na_rep=""
    )
    capsys.readouterr()

    assert main(["plot", "--run", str(legacy)]) == 0

    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert (legacy / "figures" / "seed_variability.png").is_file()


def test_aggregate_exits_nonzero_for_a_missing_run(tmp_path):
    assert main(["aggregate", "--run", str(tmp_path / "absent")]) != 0


def test_export_writes_json_and_prints_the_path(tmp_path, tiny_config, capsys):
    main(["run", "--config", str(tiny_config), "--artifacts", str(tmp_path), "--run-id", "r1"])
    run_dir = tmp_path / "r1"
    main(["aggregate", "--run", str(run_dir)])

    assert main(["export", "--run", str(run_dir)]) == 0

    output = capsys.readouterr().out
    export_path = run_dir / "export" / "results.json"
    assert str(export_path) in output
    assert export_path.is_file()


def test_export_exits_nonzero_when_the_run_has_not_been_aggregated(tmp_path, tiny_config, capsys):
    main(["run", "--config", str(tiny_config), "--artifacts", str(tmp_path), "--run-id", "r1"])
    run_dir = tmp_path / "r1"

    assert main(["export", "--run", str(run_dir)]) != 0
    assert "aggregate" in capsys.readouterr().err


def test_no_subcommand_exits_nonzero():
    assert main([]) != 0
