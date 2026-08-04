"""Stage 2 tests for the transpilation runner, persistence and resume."""

import json
import subprocess

import pandas as pd
import pytest

from routing_overhead import experiments
from routing_overhead.aggregation import aggregate_run
from routing_overhead.config import ExperimentConfig
from routing_overhead.experiments import (
    DIRECT_DEPENDENCIES,
    RESULT_COLUMNS,
    completed_experiment_ids,
    environment_metadata,
    experiment_id,
    fallback_experiment_id,
    git_state,
    prepare_run_directory,
    run_grid,
    run_single,
)

CONFIG = ExperimentConfig(
    physical_qubits=27,
    logical_qubits=(4,),
    circuit_families=("ghz_chain",),
    topologies=("complete_27", "line_27"),
    optimization_levels=(1,),
    transpiler_seeds=(11,),
    basis_gates=("rz", "sx", "x", "cx"),
)

POINT = {
    "circuit_family": "ghz_chain",
    "logical_qubits": 4,
    "topology": "line_27",
    "optimization_level": 1,
    "transpiler_seed": 11,
}


def test_experiment_id_is_deterministic():
    args = ("circuit", "topology", 1, 11, "basis")
    assert experiment_id(*args) == experiment_id(*args)
    assert len(experiment_id(*args)) == 64


@pytest.mark.parametrize("position", range(5))
def test_experiment_id_depends_on_every_component(position):
    args = ["circuit", "topology", 1, 11, "basis"]
    changed = list(args)
    changed[position] = "other" if isinstance(args[position], str) else args[position] + 1
    assert experiment_id(*args) != experiment_id(*changed)


def test_planned_point_id_is_deterministic_and_depends_on_every_axis():
    first = experiments.planned_point_id(POINT, "basis")
    assert first == experiments.planned_point_id(POINT, "basis")
    for key, other in {
        "circuit_family": "ghz_star",
        "logical_qubits": 8,
        "topology": "complete_27",
        "optimization_level": 3,
        "transpiler_seed": 22,
    }.items():
        assert first != experiments.planned_point_id({**POINT, key: other}, "basis")
    assert first != experiments.planned_point_id(POINT, "other-basis")


def test_successful_run_row_matches_the_raw_schema():
    row = run_single(CONFIG, POINT, run_id="test-run")
    assert set(row) == set(RESULT_COLUMNS)
    assert row["success"] is True
    assert row["run_id"] == "test-run"
    assert row["circuit_family"] == "ghz_chain"
    assert row["logical_qubits"] == 4
    assert row["topology"] == "line_27"
    assert row["physical_qubits"] == 27
    assert row["basis_gates"] == "rz,sx,x,cx"
    assert row["worker_count"] == 1
    assert row["input_two_qubit_count"] == 3
    assert row["output_two_qubit_count"] >= 3
    assert row["compile_time_seconds"] > 0
    assert row["exception_type"] is None
    assert row["error_message"] is None
    assert row["depth_penalty"] is None
    assert json.loads(row["circuit_settings_json"])["family"] == "ghz_chain"


def test_run_row_records_the_environment():
    row = run_single(CONFIG, POINT, run_id="test-run")
    assert row["python_version"].startswith("3.")
    assert row["qiskit_version"]
    assert row["qiskit_ibm_runtime_version"]
    assert row["platform"]


def test_failed_run_produces_an_explicit_failure_row(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("routing exploded")

    monkeypatch.setattr(experiments, "compile_circuit", boom)
    row = run_single(CONFIG, POINT, run_id="test-run")
    assert row["success"] is False
    assert row["exception_type"] == "RuntimeError"
    assert row["error_message"] == "routing exploded"
    assert row["output_depth"] is None
    assert row["compile_time_seconds"] >= 0
    assert row["input_two_qubit_count"] == 3


def test_topology_construction_failure_becomes_a_failure_row(monkeypatch):
    def boom(name):
        raise RuntimeError("topology load failed")

    monkeypatch.setattr(experiments, "build_coupling_map", boom)
    row = run_single(CONFIG, POINT, run_id="test-run")
    assert row["success"] is False
    assert row["exception_type"] == "RuntimeError"
    assert row["error_message"] == "topology load failed"
    assert row["topology"] == "line_27"
    assert row["experiment_id"]
    assert row["topology_hash"] is None


def test_circuit_construction_failure_becomes_a_failure_row(monkeypatch):
    def boom(family, num_qubits):
        raise ValueError("circuit build failed")

    monkeypatch.setattr(experiments, "_circuit", boom)
    row = run_single(CONFIG, POINT, run_id="test-run")
    assert row["success"] is False
    assert row["exception_type"] == "ValueError"
    assert row["circuit_hash"] is None
    assert row["input_depth"] is None


def test_fallback_experiment_id_is_deterministic_and_never_collides():
    first = fallback_experiment_id(POINT, "basis")
    assert first == fallback_experiment_id(POINT, "basis")
    assert first != fallback_experiment_id({**POINT, "topology": "complete_27"}, "basis")
    assert first != experiment_id("circuit", "topology", 1, 11, "basis")


def test_grid_persists_a_row_for_every_construction_failure(tmp_path, monkeypatch):
    def boom(name):
        raise RuntimeError("topology load failed")

    monkeypatch.setattr(experiments, "build_coupling_map", boom)
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    counts = run_grid(CONFIG, run_dir)

    assert counts == {"planned": 2, "executed": 2, "skipped": 0, "failed": 2}
    raw = pd.read_parquet(run_dir / "raw_results.parquet")
    assert len(raw) == 2
    assert raw["experiment_id"].nunique() == 2
    assert not raw["success"].any()


def test_circuit_metadata_failure_produces_failure_rows_instead_of_escaping(tmp_path, monkeypatch):
    def boom(family, num_qubits):
        raise RuntimeError("settings exploded")

    monkeypatch.setattr(experiments, "circuit_settings", boom)
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    counts = run_grid(CONFIG, run_dir)

    assert counts == {"planned": 2, "executed": 2, "skipped": 0, "failed": 2}
    raw = pd.read_parquet(run_dir / "raw_results.parquet")
    assert len(raw) == 2
    assert not raw["success"].any()
    assert set(raw["exception_type"]) == {"RuntimeError"}
    # The topology table is unaffected and must still be complete.
    assert len(pd.read_parquet(run_dir / "topology_metadata.parquet")) == 2


def test_topology_metadata_failure_fails_only_the_affected_points(tmp_path, monkeypatch):
    real_metadata = experiments.topology_metadata

    def boom(name):
        if name == "line_27":
            raise RuntimeError("topology metadata exploded")
        return real_metadata(name)

    monkeypatch.setattr(experiments, "topology_metadata", boom)
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    counts = run_grid(CONFIG, run_dir)

    assert counts == {"planned": 2, "executed": 2, "skipped": 0, "failed": 1}
    raw = pd.read_parquet(run_dir / "raw_results.parquet")
    assert len(raw) == 2
    failed = raw[~raw["success"]]
    assert list(failed["topology"]) == ["line_27"]
    assert list(failed["exception_type"]) == ["RuntimeError"]
    assert raw[raw["topology"] == "complete_27"]["success"].all()
    # The topology that did build keeps its complete metadata record.
    topologies = pd.read_parquet(run_dir / "topology_metadata.parquet")
    assert list(topologies["topology"]) == ["complete_27"]


def test_run_directory_is_never_overwritten(tmp_path):
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    assert run_dir.is_dir()
    with pytest.raises(FileExistsError, match="already exists"):
        prepare_run_directory(CONFIG, tmp_path, "run-a")


def test_resume_reuses_the_existing_run_directory(tmp_path):
    first = prepare_run_directory(CONFIG, tmp_path, "run-a")
    second = prepare_run_directory(CONFIG, tmp_path, "run-a", resume=True)
    assert first == second
    assert (second / "config.yaml").is_file()


def test_resume_rejects_a_different_configuration(tmp_path):
    prepare_run_directory(CONFIG, tmp_path, "run-a")
    other = ExperimentConfig(**{**CONFIG.__dict__, "transpiler_seeds": (99,)})
    with pytest.raises(ValueError, match="configuration"):
        prepare_run_directory(other, tmp_path, "run-a", resume=True)


def test_run_grid_writes_every_artifact(tmp_path):
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    counts = run_grid(CONFIG, run_dir)

    assert counts == {"planned": 2, "executed": 2, "skipped": 0, "failed": 0}
    for name in (
        "config.yaml",
        "environment.json",
        "topology_metadata.parquet",
        "circuit_metadata.parquet",
        "raw_results.parquet",
        "raw_results.csv",
    ):
        assert (run_dir / name).is_file(), name
    assert (run_dir / "logs" / "run.log").is_file()

    raw = pd.read_parquet(run_dir / "raw_results.parquet")
    assert len(raw) == 2
    assert raw["experiment_id"].nunique() == 2
    assert list(raw.columns) == list(RESULT_COLUMNS)
    assert raw["success"].all()

    topologies = pd.read_parquet(run_dir / "topology_metadata.parquet")
    assert set(topologies["topology"]) == {"complete_27", "line_27"}
    circuits = pd.read_parquet(run_dir / "circuit_metadata.parquet")
    assert len(circuits) == 1
    assert circuits.loc[0, "input_two_qubit_count"] == 3

    environment = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
    assert environment["worker_count"] == 1
    assert environment["finished_utc"]
    assert environment["config"]["basis_gates"] == ["rz", "sx", "x", "cx"]


def test_rerunning_a_completed_grid_adds_no_duplicates(tmp_path):
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    run_grid(CONFIG, run_dir)
    counts = run_grid(CONFIG, run_dir)

    assert counts == {"planned": 2, "executed": 0, "skipped": 2, "failed": 0}
    raw = pd.read_csv(run_dir / "raw_results.csv")
    assert len(raw) == 2
    assert raw["experiment_id"].nunique() == 2


def test_persistent_metadata_failure_is_terminal_on_resume(tmp_path, monkeypatch):
    def boom(family, num_qubits):
        raise RuntimeError("settings exploded")

    monkeypatch.setattr(experiments, "circuit_settings", boom)
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    first = run_grid(CONFIG, run_dir)
    before = pd.read_csv(run_dir / "raw_results.csv")

    resumed = run_grid(CONFIG, run_dir)
    after = pd.read_csv(run_dir / "raw_results.csv")

    assert first == {"planned": 2, "executed": 2, "skipped": 0, "failed": 2}
    assert resumed == {"planned": 2, "executed": 0, "skipped": 2, "failed": 0}
    assert len(after) == len(before) == 2
    assert after["planned_point_id"].nunique() == 2
    pd.testing.assert_frame_equal(after, before)


def test_aggregation_rejects_duplicate_planned_points(tmp_path):
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    run_grid(CONFIG, run_dir)
    raw_path = run_dir / "raw_results.csv"
    raw = pd.read_csv(raw_path)
    pd.concat([raw, raw.iloc[[0]]], ignore_index=True).to_csv(raw_path, index=False)

    with pytest.raises(ValueError, match="duplicate planned_point_id"):
        aggregate_run(run_dir)


def test_recovered_metadata_is_still_terminal_in_the_same_run(tmp_path, monkeypatch):
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    with monkeypatch.context() as broken:
        broken.setattr(
            experiments,
            "circuit_settings",
            lambda *args: (_ for _ in ()).throw(RuntimeError("settings exploded")),
        )
        run_grid(CONFIG, run_dir)

    resumed = run_grid(CONFIG, run_dir)
    raw = pd.read_csv(run_dir / "raw_results.csv")

    assert resumed == {"planned": 2, "executed": 0, "skipped": 2, "failed": 0}
    assert len(raw) == raw["planned_point_id"].nunique() == 2
    assert not raw["success"].any()


def test_recovered_metadata_succeeds_only_in_a_new_run(tmp_path, monkeypatch):
    with monkeypatch.context() as broken:
        broken.setattr(
            experiments,
            "circuit_settings",
            lambda *args: (_ for _ in ()).throw(RuntimeError("settings exploded")),
        )
        failed_dir = prepare_run_directory(CONFIG, tmp_path, "failed-run")
        run_grid(CONFIG, failed_dir)

    recovered_dir = prepare_run_directory(CONFIG, tmp_path, "recovered-run")
    counts = run_grid(CONFIG, recovered_dir)
    raw = pd.read_parquet(recovered_dir / "raw_results.parquet")

    assert counts == {"planned": 2, "executed": 2, "skipped": 0, "failed": 0}
    assert len(raw) == raw["planned_point_id"].nunique() == 2
    assert raw["success"].all()


def test_an_interrupted_run_resumes_without_duplicates(tmp_path):
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    real_compile = experiments.compile_circuit
    calls = {"n": 0}

    def interrupt_on_second_grid_point(circuit, *args, **kwargs):
        # The untimed warm-up compiles a 2-qubit circuit; only count real grid points.
        if circuit.num_qubits == CONFIG.logical_qubits[0]:
            calls["n"] += 1
            if calls["n"] == 2:
                raise KeyboardInterrupt
        return real_compile(circuit, *args, **kwargs)

    experiments.compile_circuit = interrupt_on_second_grid_point
    try:
        with pytest.raises(KeyboardInterrupt):
            run_grid(CONFIG, run_dir)
    finally:
        experiments.compile_circuit = real_compile

    partial = pd.read_csv(run_dir / "raw_results.csv")
    assert len(partial) == 1

    counts = run_grid(CONFIG, run_dir)
    assert counts == {"planned": 2, "executed": 1, "skipped": 1, "failed": 0}
    raw = pd.read_parquet(run_dir / "raw_results.parquet")
    assert len(raw) == 2
    assert raw["experiment_id"].nunique() == 2


def test_failures_are_persisted_as_rows_and_in_failures_csv(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("routing exploded")

    monkeypatch.setattr(experiments, "compile_circuit", boom)
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    counts = run_grid(CONFIG, run_dir)

    assert counts == {"planned": 2, "executed": 2, "skipped": 0, "failed": 2}
    raw = pd.read_parquet(run_dir / "raw_results.parquet")
    assert len(raw) == 2
    assert not raw["success"].any()
    failures = pd.read_csv(run_dir / "failures.csv")
    assert len(failures) == 2
    assert set(failures["exception_type"]) == {"RuntimeError"}
    assert "routing exploded" in (run_dir / "logs" / "run.log").read_text(encoding="utf-8")


def test_completed_experiment_ids_reads_the_journal(tmp_path):
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    assert completed_experiment_ids(run_dir) == set()
    run_grid(CONFIG, run_dir)
    assert len(completed_experiment_ids(run_dir)) == 2


def test_environment_metadata_reports_a_sequential_worker_count():
    metadata = environment_metadata()
    assert metadata["worker_count"] == 1
    assert metadata["python_version"].startswith("3.")
    assert "git_commit" in metadata
    assert "git_dirty" in metadata


def test_environment_metadata_records_every_direct_runtime_dependency():
    packages = environment_metadata()["packages"]
    assert set(packages) == set(DIRECT_DEPENDENCIES)
    assert set(DIRECT_DEPENDENCIES) >= {"matplotlib", "pyyaml"}
    assert all(version is not None for version in packages.values()), packages


def test_git_state_reports_dirty_on_an_unborn_head(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "untracked.txt").write_text("work in progress", encoding="utf-8")

    commit, dirty = git_state(tmp_path)

    assert commit is None
    assert dirty is True


def test_git_state_reports_a_bare_forty_character_sha(tmp_path):
    for command in (
        ["git", "init"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(command, cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "tracked.txt").write_text("content", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    commit, dirty = git_state(tmp_path)

    assert len(commit) == 40
    assert commit == commit.strip()
    int(commit, 16)
    assert dirty is False


def test_git_state_reports_clean_on_an_empty_unborn_repository(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    commit, dirty = git_state(tmp_path)

    assert commit is None
    assert dirty is False


def test_warm_up_compiles_before_the_first_measured_row(tmp_path, monkeypatch):
    real_compile = experiments.compile_circuit
    widths = []

    def spy(circuit, coupling_map, **kwargs):
        widths.append((circuit.num_qubits, coupling_map.size()))
        return real_compile(circuit, coupling_map, **kwargs)

    monkeypatch.setattr(experiments, "compile_circuit", spy)
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    counts = run_grid(CONFIG, run_dir)

    assert widths[0] == (2, 2), widths
    assert len(widths) == counts["executed"] + 1
    assert len(pd.read_parquet(run_dir / "raw_results.parquet")) == 2


def test_warm_up_is_skipped_when_there_is_nothing_left_to_run(tmp_path, monkeypatch):
    run_dir = prepare_run_directory(CONFIG, tmp_path, "run-a")
    run_grid(CONFIG, run_dir)

    calls = []
    monkeypatch.setattr(experiments, "compile_circuit", lambda *a, **k: calls.append(1))
    counts = run_grid(CONFIG, run_dir)

    assert counts["skipped"] == 2
    assert calls == []
