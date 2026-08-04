"""The headline figure, generated only from saved summary data."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

# Benchmark runs are headless; pick the file backend before pyplot is imported.
matplotlib.use("Agg")

import matplotlib.pyplot as plt

PRIMARY_METRIC = "two_qubit_depth_penalty"

TOPOLOGY_LABELS = {
    "complete_27": "Complete (27q)",
    "line_27": "Line (27q)",
    "cairo_heavy_hex_27": "Cairo heavy-hex (27q)",
}

# Colour carries topology, dash pattern carries optimization level, so a multi-level
# figure stays readable without doubling the number of legend colours.
TOPOLOGY_COLORS = {
    "complete_27": "C0",
    "line_27": "C1",
    "cairo_heavy_hex_27": "C2",
}

LEVEL_STYLES = {0: ":", 1: "--", 2: "-.", 3: "-"}


def plot_run(run_dir) -> list[Path]:
    """Write the two-qubit depth penalty figure as PNG and SVG; return the paths."""
    run_dir = Path(run_dir)
    summary_path = run_dir / "summary_results.parquet"
    if not summary_path.is_file():
        raise FileNotFoundError(f"{summary_path} is missing; run aggregation first")
    summary = pd.read_parquet(summary_path)
    data = summary[summary["metric"] == PRIMARY_METRIC]
    if data.empty:
        raise ValueError(f"no {PRIMARY_METRIC} rows in {summary_path}")

    families = sorted(data["circuit_family"].unique())
    figure, axes = plt.subplots(
        1, len(families), figsize=(4.5 * len(families), 4.0), squeeze=False, sharey=True
    )
    for axis, family in zip(axes[0], families):
        family_data = data[data["circuit_family"] == family]
        # One series per topology AND optimization level: the core grid holds several
        # levels, and grouping by topology alone repeats x-values and joins levels
        # into a single misleading line.
        for topology in sorted(family_data["topology"].unique()):
            for level in sorted(family_data["optimization_level"].unique()):
                series = family_data[
                    (family_data["topology"] == topology)
                    & (family_data["optimization_level"] == level)
                ].sort_values("logical_qubits")
                if series.empty:
                    continue
                label = f"{TOPOLOGY_LABELS.get(topology, topology)} L{level}"
                axis.plot(
                    series["logical_qubits"],
                    series["median"],
                    marker="o",
                    color=TOPOLOGY_COLORS.get(topology),
                    linestyle=LEVEL_STYLES.get(level, "-"),
                    label=label,
                )
                axis.fill_between(
                    series["logical_qubits"],
                    series["q25"],
                    series["q75"],
                    color=TOPOLOGY_COLORS.get(topology),
                    alpha=0.15,
                )
        axis.set_title(family)
        axis.set_xlabel("Logical qubits")
        axis.grid(alpha=0.3)
    axes[0][0].set_ylabel("Two-qubit depth penalty (ratio vs complete)")
    figure.suptitle("Two-qubit depth penalty by connectivity (median, IQR band)")
    # One shared legend below the panels: with several optimization levels an in-axes
    # legend covers the data it is describing.
    handles, labels = axes[0][0].get_legend_handles_labels()
    columns = min(3, len(labels)) or 1
    rows = -(-len(labels) // columns)
    figure.legend(handles, labels, loc="lower center", ncol=columns, frameon=False)
    figure.tight_layout(rect=(0, 0.06 + 0.045 * rows, 1, 1))

    figures_dir = run_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    paths = []
    for suffix, kwargs in ((".png", {"dpi": 300}), (".svg", {})):
        path = figures_dir / f"{PRIMARY_METRIC}{suffix}"
        figure.savefig(path, **kwargs)
        paths.append(path)
    plt.close(figure)
    return paths
