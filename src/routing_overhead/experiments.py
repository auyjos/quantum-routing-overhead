"""Sequential transpilation runner with per-run persistence and resume support."""

from __future__ import annotations

import csv
import functools
import hashlib
import json
import logging
import platform
import subprocess
import time
import traceback
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import yaml
from qiskit.transpiler import CouplingMap

from routing_overhead.circuits import build_circuit, circuit_hash, circuit_settings
from routing_overhead.config import ExperimentConfig, experiment_grid, load_config
from routing_overhead.metrics import circuit_metrics
from routing_overhead.topologies import build_coupling_map, topology_hash, topology_metadata
from routing_overhead.transpilation import compile_circuit

REPO_ROOT = Path(__file__).resolve().parents[2]

# One row per transpilation, exactly as documented in the plan's raw data schema.
RESULT_COLUMNS = (
    "run_id",
    "experiment_id",
    "planned_point_id",
    "timestamp_utc",
    "circuit_family",
    "logical_qubits",
    "circuit_hash",
    "circuit_settings_json",
    "physical_qubits",
    "topology",
    "topology_hash",
    "optimization_level",
    "transpiler_seed",
    "basis_gates",
    "input_depth",
    "input_two_qubit_depth",
    "input_two_qubit_count",
    "output_depth",
    "output_two_qubit_depth",
    "output_two_qubit_count",
    "compile_time_seconds",
    "depth_penalty",
    "two_qubit_depth_penalty",
    "two_qubit_count_penalty",
    "success",
    "exception_type",
    "error_message",
    "python_version",
    "qiskit_version",
    "qiskit_ibm_runtime_version",
    "platform",
    "cpu",
    "worker_count",
)

INTEGER_COLUMNS = (
    "logical_qubits",
    "physical_qubits",
    "optimization_level",
    "transpiler_seed",
    "input_depth",
    "input_two_qubit_depth",
    "input_two_qubit_count",
    "output_depth",
    "output_two_qubit_depth",
    "output_two_qubit_count",
    "worker_count",
)

# Sequential by design: compilation timing is only comparable under a fixed, low load.
WORKER_COUNT = 1

# Every direct runtime dependency declared in pyproject.toml, recorded per run.
DIRECT_DEPENDENCIES = (
    "qiskit",
    "qiskit-ibm-runtime",
    "numpy",
    "pandas",
    "pyarrow",
    "networkx",
    "matplotlib",
    "pyyaml",
)

RAW_CSV = "raw_results.csv"
RAW_PARQUET = "raw_results.parquet"

_LOGGER = logging.getLogger("routing_overhead.experiments")


def experiment_id(
    circuit_hash_value: str,
    topology_hash_value: str,
    optimization_level: int,
    transpiler_seed: int,
    basis_hash_value: str,
) -> str:
    """Content-derived identity for one successfully constructed transpilation."""
    key = "|".join(
        (
            circuit_hash_value,
            topology_hash_value,
            str(optimization_level),
            str(transpiler_seed),
            basis_hash_value,
        )
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def fallback_experiment_id(point: dict, basis_hash_value: str) -> str:
    """Deterministic experiment identity when content hashes are unavailable."""
    key = "|".join(
        (
            "fallback",
            point["circuit_family"],
            str(point["logical_qubits"]),
            point["topology"],
            str(point["optimization_level"]),
            str(point["transpiler_seed"]),
            basis_hash_value,
        )
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def planned_point_id(point: dict, basis_hash_value: str) -> str:
    """Stable resume identity available before circuit or topology construction."""
    key = "|".join(
        (
            "planned",
            point["circuit_family"],
            str(point["logical_qubits"]),
            point["topology"],
            str(point["optimization_level"]),
            str(point["transpiler_seed"]),
            basis_hash_value,
        )
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _settings(point: dict) -> dict:
    try:
        return circuit_settings(point["circuit_family"], point["logical_qubits"])
    except Exception:  # noqa: BLE001 - metadata must never abort a run
        return dict(point)


@functools.cache
def _circuit(family: str, num_qubits: int):
    circuit = build_circuit(family, num_qubits)
    return circuit, circuit_hash(circuit), circuit_metrics(circuit)


@functools.cache
def _topology_hash(name: str) -> str:
    return topology_hash(build_coupling_map(name))


def environment_metadata(config: ExperimentConfig | None = None, run_id: str = "") -> dict:
    """Reproducibility record for a run directory."""
    commit, dirty = git_state()
    metadata = {
        "run_id": run_id,
        "started_utc": _utc_now(),
        "finished_utc": None,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "worker_count": WORKER_COUNT,
        "git_commit": commit,
        "git_dirty": dirty,
        "packages": {name: _package_version(name) for name in DIRECT_DEPENDENCIES},
    }
    if config is not None:
        metadata["config"] = config.as_dict()
        metadata["basis_hash"] = config.basis_hash
    return metadata


def prepare_run_directory(
    config: ExperimentConfig, base_dir, run_id: str, resume: bool = False
) -> Path:
    """Create (or re-open for resume) a run directory without ever overwriting one."""
    run_dir = Path(base_dir) / run_id
    config_path = run_dir / "config.yaml"
    if run_dir.exists():
        if not resume:
            raise FileExistsError(f"run directory already exists: {run_dir}")
        stored = load_config(config_path).as_dict()
        if stored != config.as_dict():
            raise ValueError(
                f"cannot resume {run_dir}: the stored configuration differs from the one supplied"
            )
        return run_dir
    (run_dir / "logs").mkdir(parents=True)
    config_path.write_text(yaml.safe_dump(config.as_dict(), sort_keys=False), encoding="utf-8")
    (run_dir / "environment.json").write_text(
        json.dumps(environment_metadata(config, run_id), indent=2), encoding="utf-8"
    )
    return run_dir


def completed_experiment_ids(run_dir) -> set[str]:
    """Experiment keys already journalled in this run, successful or failed."""
    path = Path(run_dir) / RAW_CSV
    if not path.is_file():
        return set()
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["experiment_id"] for row in csv.DictReader(handle)}


def completed_planned_point_ids(run_dir) -> set[str]:
    """Planned points already journalled in this run, successful or failed."""
    path = Path(run_dir) / RAW_CSV
    if not path.is_file():
        return set()
    return set(read_raw_results(run_dir)["planned_point_id"])


def run_single(
    config: ExperimentConfig, point: dict, run_id: str, metadata_error: BaseException | None = None
) -> dict:
    """Compile one grid point and return its result row; failures become rows too.

    Circuit and topology construction happen inside the failure capture, so a broken
    builder, a failed Cairo load or a hashing error is persisted instead of aborting
    the grid. `metadata_error` fails the point without compiling, so a run can never
    report success for a point whose required metadata record is missing.
    `compile_time_seconds` holds compile-only time on success and the elapsed time
    before the exception on failure.
    """
    row = _blank_row(config, point, run_id)
    started = time.perf_counter()
    try:
        if metadata_error is not None:
            raise metadata_error
        circuit, circuit_hash_value, input_metrics = _circuit(
            point["circuit_family"], point["logical_qubits"]
        )
        coupling_map = build_coupling_map(point["topology"])
        topology_hash_value = _topology_hash(point["topology"])
        row["circuit_hash"] = circuit_hash_value
        row["topology_hash"] = topology_hash_value
        row["experiment_id"] = experiment_id(
            circuit_hash_value,
            topology_hash_value,
            point["optimization_level"],
            point["transpiler_seed"],
            config.basis_hash,
        )
        row["input_depth"] = input_metrics["depth"]
        row["input_two_qubit_depth"] = input_metrics["two_qubit_depth"]
        row["input_two_qubit_count"] = input_metrics["two_qubit_count"]

        compile_started = time.perf_counter()
        compiled = compile_circuit(
            circuit,
            coupling_map,
            optimization_level=point["optimization_level"],
            seed_transpiler=point["transpiler_seed"],
            basis_gates=config.basis_gates,
        )
        row["compile_time_seconds"] = time.perf_counter() - compile_started
        output_metrics = circuit_metrics(compiled)
        row["output_depth"] = output_metrics["depth"]
        row["output_two_qubit_depth"] = output_metrics["two_qubit_depth"]
        row["output_two_qubit_count"] = output_metrics["two_qubit_count"]
    except Exception as error:  # noqa: BLE001 - every failure must still produce a row
        row["compile_time_seconds"] = time.perf_counter() - started
        row["success"] = False
        row["exception_type"] = type(error).__name__
        row["error_message"] = str(error)
        _LOGGER.error(
            "run failed: %s n=%s %s level=%s seed=%s\n%s",
            point["circuit_family"],
            point["logical_qubits"],
            point["topology"],
            point["optimization_level"],
            point["transpiler_seed"],
            traceback.format_exc(),
        )
    return row


def _blank_row(config: ExperimentConfig, point: dict, run_id: str) -> dict:
    """Row skeleton that is valid even if nothing about this point can be built."""
    return {
        "run_id": run_id,
        "experiment_id": fallback_experiment_id(point, config.basis_hash),
        "planned_point_id": planned_point_id(point, config.basis_hash),
        "timestamp_utc": _utc_now(),
        "circuit_family": point["circuit_family"],
        "logical_qubits": point["logical_qubits"],
        "circuit_hash": None,
        "circuit_settings_json": json.dumps(_settings(point), sort_keys=True),
        "physical_qubits": config.physical_qubits,
        "topology": point["topology"],
        "topology_hash": None,
        "optimization_level": point["optimization_level"],
        "transpiler_seed": point["transpiler_seed"],
        "basis_gates": ",".join(config.basis_gates),
        "input_depth": None,
        "input_two_qubit_depth": None,
        "input_two_qubit_count": None,
        "output_depth": None,
        "output_two_qubit_depth": None,
        "output_two_qubit_count": None,
        "compile_time_seconds": None,
        # Penalties need the complete-connectivity baseline; aggregation fills them in.
        "depth_penalty": None,
        "two_qubit_depth_penalty": None,
        "two_qubit_count_penalty": None,
        "success": True,
        "exception_type": None,
        "error_message": None,
        "python_version": platform.python_version(),
        "qiskit_version": _package_version("qiskit"),
        "qiskit_ibm_runtime_version": _package_version("qiskit-ibm-runtime"),
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "worker_count": WORKER_COUNT,
    }


def run_grid(config: ExperimentConfig, run_dir, on_result=None) -> dict:
    """Execute every outstanding grid point sequentially, journalling each row."""
    run_dir = Path(run_dir)
    handler = _attach_log_file(run_dir / "logs" / "run.log")
    try:
        metadata_errors = _write_metadata_tables(config, run_dir)
        done = completed_planned_point_ids(run_dir)
        counts = {"planned": config.size(), "executed": 0, "skipped": 0, "failed": 0}
        warmed_up = False
        for index, point in enumerate(experiment_grid(config), start=1):
            if planned_point_id(point, config.basis_hash) in done:
                counts["skipped"] += 1
                continue
            metadata_error = metadata_errors["topologies"].get(
                point["topology"]
            ) or metadata_errors["circuits"].get((point["circuit_family"], point["logical_qubits"]))
            if metadata_error is None and not warmed_up:
                _warm_up(config)
                warmed_up = True
            row = run_single(config, point, run_id=run_dir.name, metadata_error=metadata_error)
            _append_row(run_dir / RAW_CSV, row)
            done.add(row["planned_point_id"])
            counts["executed"] += 1
            counts["failed"] += 0 if row["success"] else 1
            if on_result is not None:
                on_result(index, counts["planned"], row)
            _LOGGER.info(
                "%s n=%s %s level=%s seed=%s success=%s",
                point["circuit_family"],
                point["logical_qubits"],
                point["topology"],
                point["optimization_level"],
                point["transpiler_seed"],
                row["success"],
            )
        _finalize(config, run_dir)
        return counts
    finally:
        _LOGGER.removeHandler(handler)
        handler.close()


def _warm_up(config: ExperimentConfig) -> None:
    """One untimed compile before the first measured row.

    Qiskit's first `generate_preset_pass_manager` call pays a large one-time
    initialization cost (measured at ~260x the median compile in an earlier run).
    Without this, that cost is billed entirely to whichever grid point happens to be
    first, biasing every compile-time comparison.
    """
    try:
        compile_circuit(
            build_circuit("ghz_chain", 2),
            CouplingMap.from_line(2, bidirectional=True),
            optimization_level=config.optimization_levels[0],
            seed_transpiler=config.transpiler_seeds[0],
            basis_gates=config.basis_gates,
        )
    except Exception:  # noqa: BLE001 - a failed warm-up must not abort the grid
        _LOGGER.warning("compiler warm-up failed\n%s", traceback.format_exc())


def read_raw_results(run_dir) -> pd.DataFrame:
    """Load the journalled rows with the documented column order and integer types."""
    frame = pd.read_csv(Path(run_dir) / RAW_CSV)
    duplicates = frame["planned_point_id"].duplicated()
    if duplicates.any():
        raise ValueError(
            f"raw results contain {int(duplicates.sum())} duplicate planned_point_id rows"
        )
    for column in INTEGER_COLUMNS:
        frame[column] = frame[column].astype("Int64")
    frame["success"] = frame["success"].astype(bool)
    return frame[list(RESULT_COLUMNS)]


def _finalize(config: ExperimentConfig, run_dir: Path) -> None:
    frame = read_raw_results(run_dir)
    atomic_write(run_dir / RAW_PARQUET, lambda path: frame.to_parquet(path, index=False))
    failures = frame[~frame["success"]]
    if len(failures):
        atomic_write(run_dir / "failures.csv", lambda path: failures.to_csv(path, index=False))
    environment_path = run_dir / "environment.json"
    environment = json.loads(environment_path.read_text(encoding="utf-8"))
    environment["finished_utc"] = _utc_now()
    environment["rows"] = len(frame)
    environment["failures"] = len(failures)
    atomic_write(
        environment_path,
        lambda path: path.write_text(json.dumps(environment, indent=2), encoding="utf-8"),
    )


def _write_metadata_tables(config: ExperimentConfig, run_dir: Path) -> dict:
    """Write the metadata tables and report which records could not be assembled.

    Topology and circuit metadata are required evidence for a run. Assembling a record
    must never abort the grid, and a missing record must never be silently paired with
    successful result rows: every affected grid point is failed explicitly instead.
    """
    topologies = []
    topology_errors: dict = {}
    for name in config.topologies:
        try:
            metadata = topology_metadata(name)
            metadata["edge_list_json"] = json.dumps(
                [list(edge) for edge in _undirected_edges(name)]
            )
            topologies.append(metadata)
        except Exception as error:  # noqa: BLE001 - affected points become failure rows
            topology_errors[name] = error
            _LOGGER.error("topology metadata failed for %s\n%s", name, traceback.format_exc())
    topology_frame = pd.DataFrame(topologies)
    atomic_write(
        run_dir / "topology_metadata.parquet",
        lambda path: topology_frame.to_parquet(path, index=False),
    )

    circuits = []
    circuit_errors: dict = {}
    for family in config.circuit_families:
        for num_qubits in config.logical_qubits:
            try:
                circuit, circuit_hash_value, metrics = _circuit(family, num_qubits)
                record = {
                    "circuit_family": family,
                    "logical_qubits": num_qubits,
                    "circuit_hash": circuit_hash_value,
                    "circuit_settings_json": json.dumps(
                        circuit_settings(family, num_qubits), sort_keys=True
                    ),
                    "input_depth": metrics["depth"],
                    "input_two_qubit_depth": metrics["two_qubit_depth"],
                    "input_two_qubit_count": metrics["two_qubit_count"],
                    "input_operation_counts_json": json.dumps(
                        dict(sorted(circuit.count_ops().items()))
                    ),
                }
            except Exception as error:  # noqa: BLE001 - affected points become failure rows
                circuit_errors[(family, num_qubits)] = error
                _LOGGER.error(
                    "circuit metadata failed for %s n=%s\n%s",
                    family,
                    num_qubits,
                    traceback.format_exc(),
                )
                continue
            circuits.append(record)
    circuit_frame = pd.DataFrame(circuits)
    atomic_write(
        run_dir / "circuit_metadata.parquet",
        lambda path: circuit_frame.to_parquet(path, index=False),
    )
    return {"topologies": topology_errors, "circuits": circuit_errors}


def _undirected_edges(name: str):
    from routing_overhead.topologies import undirected_edges

    return undirected_edges(build_coupling_map(name))


def atomic_write(path, write) -> None:
    """Write through a sibling temporary file, then replace the target in one step.

    `raw_results.csv` is the resume journal. A crash partway through rewriting it must
    leave the previous valid file in place rather than a truncated one.
    """
    path = Path(path)
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        write(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _append_row(path: Path, row: dict) -> None:
    is_new = not path.is_file()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(RESULT_COLUMNS))
        if is_new:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()


def _attach_log_file(path: Path) -> logging.Handler:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _LOGGER.setLevel(logging.INFO)
    _LOGGER.addHandler(handler)
    return handler


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except Exception:  # noqa: BLE001 - a missing optional package must not break a run
        return None


def git_state(repo_dir=REPO_ROOT) -> tuple[str | None, bool | None]:
    """Commit SHA and dirty flag, each resolved independently.

    On an unborn HEAD `rev-parse` fails but `status` still works, so the truthful
    answer is `(None, True/False)` rather than `(None, None)`.
    """
    commit = _git(["rev-parse", "HEAD"], repo_dir)
    status = _git(["status", "--porcelain"], repo_dir)
    return commit, None if status is None else bool(status)


def _git(arguments: list[str], repo_dir) -> str | None:
    try:
        return subprocess.run(
            ["git", *arguments],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_dir,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - missing git or repository must not break a run
        return None


def default_run_id(config_path) -> str:
    """Timestamped, collision-resistant run identifier derived from the config name."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{Path(config_path).stem}"


__all__ = [
    "RESULT_COLUMNS",
    "completed_experiment_ids",
    "completed_planned_point_ids",
    "default_run_id",
    "environment_metadata",
    "experiment_id",
    "planned_point_id",
    "prepare_run_directory",
    "read_raw_results",
    "run_grid",
    "run_single",
]
