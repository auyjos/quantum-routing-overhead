"""JSON export of a run's summary, raw results, and topology metadata.

Everything here is read back from the same files `plotting.py` draws from
(`summary_results.parquet`, `raw_results.csv`, `topology_metadata.parquet`,
`environment.json`), so the export can never disagree with the poster figures.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from routing_overhead.experiments import atomic_write, read_raw_results

EXPORT_FILENAME = "results.json"

RAW_EXPORT_COLUMNS = (
    "circuit_family",
    "logical_qubits",
    "topology",
    "optimization_level",
    "transpiler_seed",
    "output_depth",
    "output_two_qubit_depth",
    "output_two_qubit_count",
    "compile_time_seconds",
    "depth_penalty",
    "two_qubit_depth_penalty",
    "two_qubit_count_penalty",
    "success",
)

TOPOLOGY_EXPORT_COLUMNS = (
    "topology",
    "physical_qubits",
    "undirected_edges",
    "min_degree",
    "max_degree",
    "mean_degree",
    "diameter",
    "average_shortest_path_length",
    "edge_list_json",
)


def export_run(run_dir) -> dict:
    """Write `<run_dir>/export/results.json` and report what went into it."""
    run_dir = Path(run_dir)
    summary_path = run_dir / "summary_results.parquet"
    if not summary_path.is_file():
        raise FileNotFoundError(f"no summary results in {run_dir}; run aggregate first")

    environment = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
    summary = pd.read_parquet(summary_path)
    raw = read_raw_results(run_dir)[list(RAW_EXPORT_COLUMNS)]
    topologies = pd.read_parquet(run_dir / "topology_metadata.parquet")[
        list(TOPOLOGY_EXPORT_COLUMNS)
    ]
    topologies = topologies.assign(
        edge_list=topologies["edge_list_json"].map(json.loads)
    ).drop(columns=["edge_list_json"])

    payload = {
        "provenance": {
            "run_id": environment["run_id"],
            "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "git_commit": environment.get("git_commit"),
            "python_version": environment.get("python_version"),
            "qiskit_version": environment.get("packages", {}).get("qiskit"),
            "config": environment.get("config"),
        },
        "topologies": _records(topologies),
        "summary": _records(summary),
        "raw": _records(raw),
    }

    export_dir = run_dir / "export"
    export_dir.mkdir(exist_ok=True)
    path = export_dir / EXPORT_FILENAME
    atomic_write(
        path, lambda p: Path(p).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    )
    return {"path": path, "summary_rows": len(summary), "raw_rows": len(raw)}


def _records(frame: pd.DataFrame) -> list[dict]:
    """`DataFrame.to_dict` by way of a NaN -> null pass, for strict JSON readers."""
    return [{key: _json_safe(value) for key, value in row.items()} for row in frame.to_dict("records")]


def _json_safe(value):
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, (int, float, bool, str)):
        return value
    return value.item() if hasattr(value, "item") else value
