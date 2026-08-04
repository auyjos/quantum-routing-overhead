"""Poster figures, generated only from saved run data.

Every value drawn here is read back from `summary_results.parquet`,
`raw_results.csv` or `topology_metadata.parquet`. Nothing is recomputed from
circuits and no result value is written by hand.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib
import pandas as pd

# Benchmark runs are headless; pick the file backend before pyplot is imported.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.ticker import ScalarFormatter

from routing_overhead.experiments import read_raw_results

_LOGGER = logging.getLogger("routing_overhead.plotting")

PRIMARY_METRIC = "two_qubit_depth_penalty"
COUNT_METRIC = "two_qubit_count_penalty"
BASELINE_TOPOLOGY = "complete_27"
GHZ_FAMILIES = ("ghz_chain", "ghz_star")

FIGURE_NAMES = (
    "topology_comparison",
    PRIMARY_METRIC,
    COUNT_METRIC,
    "ghz_chain_vs_star",
    "optimization_quality_vs_time",
    "seed_variability",
)

TOPOLOGY_LABELS = {
    "complete_27": "Complete (27q)",
    "line_27": "Line (27q)",
    "cairo_heavy_hex_27": "Cairo heavy-hex (27q)",
}

TOPOLOGY_SHORT = {
    "complete_27": "complete",
    "line_27": "line",
    "cairo_heavy_hex_27": "heavy-hex",
}

# Colour carries topology, dash pattern carries optimization level, so a multi-level
# figure stays readable without doubling the number of legend colours.
TOPOLOGY_COLORS = {
    "complete_27": "C0",
    "line_27": "C1",
    "cairo_heavy_hex_27": "C2",
}

TOPOLOGY_LINESTYLES = {"complete_27": "-", "line_27": "-", "cairo_heavy_hex_27": "--"}

LEVEL_STYLES = {0: ":", 1: "--", 2: "-.", 3: "-"}

FAMILY_LABELS = {
    "qft": "QFT",
    "ghz_chain": "GHZ chain",
    "ghz_star": "GHZ star",
    "efficient_su2": "Efficient SU(2)",
}

FAMILY_COLORS = {"ghz_chain": "C3", "ghz_star": "C4"}

METRIC_LABELS = {
    PRIMARY_METRIC: "Two-qubit depth penalty (× vs complete)",
    COUNT_METRIC: "Two-qubit gate-count penalty (× vs complete)",
}

BASELINE_LABEL = "Complete connectivity (penalty = 1)"

# Line and Cairo land within a fraction of a millisecond of each other at every level, and
# which of the two sits higher changes between levels, so the labels are separated
# horizontally — line to the left of its marker, Cairo to the right — rather than
# vertically, which only works while the vertical order holds.
TIMING_LABEL_OFFSETS = {
    "complete_27": (9, 7),
    "line_27": (-26, -6),
    "cairo_heavy_hex_27": (10, -6),
}

METRIC_TITLES = {
    PRIMARY_METRIC: "Two-qubit depth penalty by connectivity (median, IQR band)",
    COUNT_METRIC: "Two-qubit gate-count penalty by connectivity (median, IQR band)",
}

# A0 poster viewing distance: everything one size up from a paper figure.
POSTER_STYLE = {
    "font.size": 12,
    "axes.titlesize": 14,
    "axes.labelsize": 13,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 11,
    "figure.titlesize": 17,
    "savefig.bbox": "tight",
}

TIMING_NOTE = (
    "Compilation time is a local single-machine measurement, not hardware performance. "
    "Bars show the interquartile range."
)

# A repeat may only contribute timing observations if every non-time output it recorded
# is identical to the canonical run for the same planned point.
TIMING_MATCH_COLUMNS = (
    "circuit_family",
    "logical_qubits",
    "topology",
    "optimization_level",
    "transpiler_seed",
    "basis_gates",
    "circuit_hash",
    "topology_hash",
    "experiment_id",
    "output_depth",
    "output_two_qubit_depth",
    "output_two_qubit_count",
)

CELL_KEYS = ("topology", "circuit_family", "logical_qubits", "optimization_level")


def plot_run(run_dir, timing_runs=()) -> list[Path]:
    """Write the poster figure set as PNG and SVG; return the paths written.

    `timing_runs` are additional full-grid run directories collected as process
    repeats. They are used only for the compilation-time figure, which is skipped
    when none are supplied. Any other figure whose saved inputs are missing — a
    smoke run has no QFT rows and no GHZ pair, for example — is skipped rather
    than drawn from partial data.
    """
    run_dir = Path(run_dir)
    summary_path = run_dir / "summary_results.parquet"
    if not summary_path.is_file():
        raise FileNotFoundError(f"{summary_path} is missing; run aggregation first")
    summary = pd.read_parquet(summary_path)
    if summary[summary["metric"] == PRIMARY_METRIC].empty:
        raise ValueError(f"no {PRIMARY_METRIC} rows in {summary_path}")

    figures_dir = run_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    raw = _raw_results(run_dir)
    paths: list[Path] = []
    with plt.rc_context(POSTER_STYLE):
        paths += _topology_figure(run_dir, figures_dir)
        paths += _penalty_figure(summary, PRIMARY_METRIC, figures_dir)
        paths += _penalty_figure(summary, COUNT_METRIC, figures_dir)
        paths += _ghz_figure(summary, figures_dir)
        paths += _timing_figure(run_dir, timing_runs, raw, figures_dir)
        paths += _seed_variability_figure(raw, figures_dir)
    return paths


def pooled_compile_times(run_dir, timing_runs) -> pd.DataFrame:
    """Stack the canonical and repeat compile times after exact planned-point matching.

    The repeats exist to show how much compilation time moves between processes.
    Pooling them is only meaningful if they compiled the same grid to the same
    output, so a repeat that differs in any non-time field is rejected instead of
    quietly averaged in.
    """
    canonical = _successes(_timing_frame(run_dir))
    frames = [canonical.assign(source_run=Path(run_dir).name)]
    for repeat_dir in timing_runs:
        repeat_dir = Path(repeat_dir)
        repeat = _successes(_timing_frame(repeat_dir))
        _require_matching_points(canonical, repeat, repeat_dir.name)
        frames.append(repeat.assign(source_run=repeat_dir.name))
    columns = ["planned_point_id", *TIMING_MATCH_COLUMNS, "compile_time_seconds", "source_run"]
    return pd.concat([frame[columns] for frame in frames], ignore_index=True)


def _timing_frame(run_dir) -> pd.DataFrame:
    """Strict read for timing pooling: no planned-point identity, no pooling."""
    run_dir = Path(run_dir)
    path = run_dir / "raw_results.csv"
    if path.is_file() and "planned_point_id" not in pd.read_csv(path, nrows=0).columns:
        raise ValueError(
            f"{run_dir} was collected before planned_point_id existed; pooling compilation "
            "times requires exact planned-point matching, so this run cannot be pooled"
        )
    return read_raw_results(run_dir)


def _require_matching_points(canonical: pd.DataFrame, repeat: pd.DataFrame, name: str) -> None:
    left = canonical.set_index("planned_point_id").sort_index()
    right = repeat.set_index("planned_point_id").sort_index()
    missing = left.index.difference(right.index)
    extra = right.index.difference(left.index)
    if len(missing) or len(extra):
        raise ValueError(
            f"timing repeat {name} does not cover the canonical grid: "
            f"{len(missing)} missing and {len(extra)} extra planned point(s)"
        )
    right = right.loc[left.index]
    differing = [
        column for column in TIMING_MATCH_COLUMNS if not left[column].equals(right[column])
    ]
    if differing:
        raise ValueError(
            f"timing repeat {name} does not reproduce the canonical run; "
            f"differing column(s): {', '.join(differing)}"
        )


def _topology_figure(run_dir: Path, figures_dir: Path) -> list[Path]:
    path = run_dir / "topology_metadata.parquet"
    if not path.is_file():
        return _skip("topology_comparison", f"{path.name} is missing")
    frame = pd.read_parquet(path)
    if "edge_list_json" not in frame.columns or frame.empty:
        return _skip("topology_comparison", "no saved edge lists in topology metadata")
    order = [name for name in TOPOLOGY_LABELS if name in set(frame["topology"])]
    frame = frame.set_index("topology").reindex(order)

    figure, axes = plt.subplots(1, len(frame), figsize=(5.0 * len(frame), 5.4), squeeze=False)
    for axis, (name, row) in zip(axes[0], frame.iterrows()):
        edges = [tuple(edge) for edge in json.loads(row["edge_list_json"])]
        graph = nx.Graph()
        graph.add_nodes_from(range(int(row["physical_qubits"])))
        graph.add_edges_from(edges)
        positions = nx.kamada_kawai_layout(graph)
        # The complete map carries 351 couplings; drawn opaque it is a solid disc that
        # hides the nodes, so dense maps get a lighter, thinner edge stroke.
        dense = len(edges) > 60
        nx.draw_networkx_edges(
            graph,
            positions,
            ax=axis,
            width=0.4 if dense else 1.4,
            alpha=0.10 if dense else 0.75,
            edge_color="0.25",
        )
        nx.draw_networkx_nodes(
            graph,
            positions,
            ax=axis,
            node_size=170,
            node_color=TOPOLOGY_COLORS.get(name, "C7"),
            linewidths=0.5,
            edgecolors="white",
        )
        axis.set_title(
            f"{TOPOLOGY_LABELS.get(name, name)}\n"
            f"{int(row['undirected_edges'])} couplings · degree "
            f"{int(row['min_degree'])}–{int(row['max_degree'])} · diameter "
            f"{int(row['diameter'])}"
        )
        axis.set_axis_off()
    figure.suptitle("Connectivity models compared (saved coupling-map edge lists)")
    figure.text(
        0.5,
        0.02,
        "Undirected coupling maps only; no calibration or gate-direction data is used.",
        ha="center",
        fontsize=11,
    )
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    return _save(figure, figures_dir, "topology_comparison")


def _penalty_figure(summary: pd.DataFrame, metric: str, figures_dir: Path) -> list[Path]:
    # The complete-connectivity series is the denominator of the ratio, so it is 1.0 at
    # every point by construction. Drawn per level it adds three flat lines and three
    # legend entries that carry no information; one labelled baseline says the same.
    data = summary[(summary["metric"] == metric) & (summary["topology"] != BASELINE_TOPOLOGY)]
    if data.empty:
        return _skip(metric, f"no constrained-topology {metric} rows in the summary table")

    families = sorted(data["circuit_family"].unique())
    figure, axes = plt.subplots(
        1, len(families), figsize=(4.8 * len(families), 4.4), squeeze=False, sharey=True
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
        axis.axhline(1.0, color="0.4", linestyle=":", linewidth=1.2, label=BASELINE_LABEL)
        axis.set_title(FAMILY_LABELS.get(family, family))
        axis.set_xlabel("Logical qubits")
        axis.set_xticks(sorted(family_data["logical_qubits"].unique()))
        axis.grid(alpha=0.3)
    _ratio_ylim(axes[0][0], data)
    axes[0][0].set_ylabel(METRIC_LABELS.get(metric, metric))
    figure.suptitle(METRIC_TITLES.get(metric, metric))
    _shared_legend(figure, axes[0][0])
    return _save(figure, figures_dir, metric)


def _ghz_figure(summary: pd.DataFrame, figures_dir: Path) -> list[Path]:
    data = summary[
        (summary["metric"] == PRIMARY_METRIC)
        & summary["circuit_family"].isin(GHZ_FAMILIES)
        & (summary["topology"] != BASELINE_TOPOLOGY)
    ]
    if set(data["circuit_family"].unique()) != set(GHZ_FAMILIES):
        return _skip("ghz_chain_vs_star", "the run has no GHZ chain/star pair on a constrained map")

    levels = sorted(data["optimization_level"].unique())
    figure, axes = plt.subplots(
        1, len(levels), figsize=(4.8 * len(levels), 4.6), squeeze=False, sharey=True
    )
    for axis, level in zip(axes[0], levels):
        level_data = data[data["optimization_level"] == level]
        for family in GHZ_FAMILIES:
            for topology in sorted(level_data["topology"].unique()):
                series = level_data[
                    (level_data["circuit_family"] == family) & (level_data["topology"] == topology)
                ].sort_values("logical_qubits")
                if series.empty:
                    continue
                axis.plot(
                    series["logical_qubits"],
                    series["median"],
                    marker="o" if family == "ghz_chain" else "s",
                    color=FAMILY_COLORS[family],
                    linestyle=TOPOLOGY_LINESTYLES.get(topology, "-"),
                    label=f"{FAMILY_LABELS[family]} on {TOPOLOGY_SHORT.get(topology, topology)}",
                )
                axis.fill_between(
                    series["logical_qubits"],
                    series["q25"],
                    series["q75"],
                    color=FAMILY_COLORS[family],
                    alpha=0.13,
                )
        axis.axhline(
            1.0,
            color="0.4",
            linestyle=":",
            linewidth=1.2,
            label=BASELINE_LABEL,
        )
        axis.set_title(f"Optimization level {level}")
        axis.set_xlabel("Logical qubits")
        axis.set_xticks(sorted(level_data["logical_qubits"].unique()))
        axis.grid(alpha=0.3)
    _ratio_ylim(axes[0][0], data)
    axes[0][0].set_ylabel(METRIC_LABELS[PRIMARY_METRIC])
    figure.suptitle("Chain-shaped versus star-shaped interaction: routing cost (median, IQR band)")
    _shared_legend(figure, axes[0][0])
    return _save(figure, figures_dir, "ghz_chain_vs_star")


def _timing_figure(
    run_dir: Path, timing_runs, raw: pd.DataFrame | None, figures_dir: Path
) -> list[Path]:
    timing_runs = list(timing_runs)
    if not timing_runs:
        return _skip("optimization_quality_vs_time", "no repeat timing runs were supplied")
    if raw is None:
        return _skip("optimization_quality_vs_time", "raw results are missing")
    pooled = pooled_compile_times(run_dir, timing_runs)
    quality = _successes(raw)
    quality = quality[quality[PRIMARY_METRIC].notna()]
    if quality.empty:
        return _skip("optimization_quality_vs_time", f"no {PRIMARY_METRIC} values in raw results")

    figure, axis = plt.subplots(figsize=(9.0, 6.0))
    for topology in [name for name in TOPOLOGY_LABELS if name in set(pooled["topology"])]:
        times, penalties, x_error, y_error, levels = [], [], [[], []], [[], []], []
        for level in sorted(pooled["optimization_level"].unique()):
            observed = (
                pooled[(pooled["topology"] == topology) & (pooled["optimization_level"] == level)][
                    "compile_time_seconds"
                ]
                * 1000.0
            )
            scores = quality[
                (quality["topology"] == topology) & (quality["optimization_level"] == level)
            ][PRIMARY_METRIC].astype(float)
            if observed.empty or scores.empty:
                continue
            times.append(observed.median())
            penalties.append(scores.median())
            x_error[0].append(observed.median() - observed.quantile(0.25))
            x_error[1].append(observed.quantile(0.75) - observed.median())
            y_error[0].append(scores.median() - scores.quantile(0.25))
            y_error[1].append(scores.quantile(0.75) - scores.median())
            levels.append(level)
        if not times:
            continue
        axis.errorbar(
            times,
            penalties,
            xerr=x_error,
            yerr=y_error,
            marker="o",
            capsize=3,
            linewidth=1.6,
            color=TOPOLOGY_COLORS.get(topology),
            label=TOPOLOGY_LABELS.get(topology, topology),
        )
        offset = TIMING_LABEL_OFFSETS.get(topology, (8, 7))
        for x, y, level in zip(times, penalties, levels):
            axis.annotate(f"L{level}", (x, y), textcoords="offset points", xytext=offset)

    processes = pooled["source_run"].nunique()
    seeds = quality["transpiler_seed"].nunique()
    axis.set_xlabel(
        f"Pooled median compilation time per transpilation (ms, log scale), "
        f"{processes} process repeats × {seeds} transpiler seeds (crossed)"
    )
    axis.set_ylabel(f"Median {METRIC_LABELS[PRIMARY_METRIC].lower()}")
    # Times span 2 ms to 46 ms: on a linear axis every constrained point collapses into
    # one cluster. The axis is logarithmic and labelled in real milliseconds, not
    # rescaled or truncated.
    axis.set_xscale("log")
    axis.xaxis.set_major_formatter(ScalarFormatter())
    axis.xaxis.set_minor_formatter(ScalarFormatter())
    axis.tick_params(axis="x", which="minor", labelsize=9)
    axis.set_ylim(bottom=0)
    axis.grid(alpha=0.3)
    axis.legend(frameon=False)
    figure.suptitle("Optimization level: output quality against compilation time")
    figure.text(0.5, 0.005, TIMING_NOTE, ha="center", fontsize=11)
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    return _save(figure, figures_dir, "optimization_quality_vs_time")


def _seed_variability_figure(raw: pd.DataFrame | None, figures_dir: Path) -> list[Path]:
    if raw is None:
        return _skip("seed_variability", "raw results are missing")
    data = _successes(raw)
    data = data[(data["topology"] != BASELINE_TOPOLOGY) & data[PRIMARY_METRIC].notna()]
    if data.empty:
        return _skip("seed_variability", "no constrained-topology penalties in raw results")

    # Data-driven selection: the highest-overhead configuration of every circuit family
    # on every constrained map, so the panel is not hand-picked.
    cells = (
        data.groupby(list(CELL_KEYS))[PRIMARY_METRIC]
        .median()
        .reset_index()
        # Highest median first; ties resolved towards the largest circuit, because a
        # family that never pays a penalty on a map (GHZ chain on a line) is the more
        # informative statement at the largest size tested.
        .sort_values([PRIMARY_METRIC, *CELL_KEYS], ascending=[False, True, True, False, True])
    )
    selected = cells.drop_duplicates(subset=["topology", "circuit_family"], keep="first")

    series, labels, colors = [], [], []
    for cell in selected.itertuples(index=False):
        rows = data
        for key in CELL_KEYS:
            rows = rows[rows[key] == getattr(cell, key)]
        series.append(rows.sort_values("transpiler_seed")[PRIMARY_METRIC].astype(float).tolist())
        labels.append(
            f"{FAMILY_LABELS.get(cell.circuit_family, cell.circuit_family)}\n"
            f"n={cell.logical_qubits} · L{cell.optimization_level}\n"
            f"{TOPOLOGY_SHORT.get(cell.topology, cell.topology)}"
        )
        colors.append(TOPOLOGY_COLORS.get(cell.topology, "C7"))

    figure, axis = plt.subplots(figsize=(max(8.0, 1.5 * len(series)), 5.6))
    artists = axis.boxplot(series, patch_artist=True, widths=0.6)
    for patch, color in zip(artists["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.45)
    for median in artists["medians"]:
        median.set_color("black")
    axis.set_xticks(range(1, len(labels) + 1))
    axis.set_xticklabels(labels)
    axis.set_ylabel(METRIC_LABELS[PRIMARY_METRIC])
    axis.set_ylim(bottom=0)
    axis.axhline(1.0, color="0.4", linestyle=":", linewidth=1.2)
    axis.grid(alpha=0.3, axis="y")
    seeds = data["transpiler_seed"].nunique()
    figure.suptitle("Seed variability at the highest-overhead configuration of each family and map")
    figure.text(
        0.5,
        0.005,
        f"Each box: {seeds} fixed transpiler seeds for one configuration. "
        "Dotted line marks the complete-connectivity baseline.",
        ha="center",
        fontsize=11,
    )
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    return _save(figure, figures_dir, "seed_variability")


def _ratio_ylim(axis, data: pd.DataFrame) -> None:
    """Zero-based ratio axis covering every panel.

    A truncated ratio axis exaggerates differences, and because the panels share the
    y-axis the limit must be set once from the whole faceted frame — set per panel it
    would freeze on the first facet and clip the later ones.
    """
    top = float(max(data["median"].max(), data["q75"].max()))
    axis.set_ylim(0, top * 1.06)


def _shared_legend(figure, axis) -> None:
    """One legend below the panels: an in-axes legend covers the data it describes."""
    handles, labels = axis.get_legend_handles_labels()
    columns = min(3, len(labels)) or 1
    rows = -(-len(labels) // columns)
    figure.legend(handles, labels, loc="lower center", ncol=columns, frameon=False)
    figure.tight_layout(rect=(0, 0.06 + 0.045 * rows, 1, 1))


def _save(figure, figures_dir: Path, name: str) -> list[Path]:
    paths = []
    for suffix, kwargs in ((".png", {"dpi": 300}), (".svg", {})):
        path = figures_dir / f"{name}{suffix}"
        figure.savefig(path, **kwargs)
        paths.append(path)
    plt.close(figure)
    return paths


def _skip(name: str, reason: str) -> list[Path]:
    _LOGGER.warning("skipped figure %s: %s", name, reason)
    return []


def _raw_results(run_dir: Path) -> pd.DataFrame | None:
    """Load the raw journal for plotting, tolerating pre-`planned_point_id` runs.

    `read_raw_results` is the strict reader: resume and aggregation depend on the
    planned-point identity and must keep failing without it. Plotting only needs the
    metric columns, and the earliest smoke runs were journalled before that column
    existed, so a figure pass reads those directly instead of refusing to draw.

    The fallback loses the strict reader's duplicate-point check, so the content-derived
    `experiment_id` stands in for it: a journal that repeats a point would silently
    double-weight it in every median, IQR and box, which is worse than not plotting.
    """
    path = run_dir / "raw_results.csv"
    if not path.is_file():
        return None
    if "planned_point_id" in pd.read_csv(path, nrows=0).columns:
        return read_raw_results(run_dir)
    _LOGGER.warning(
        "%s was collected before planned_point_id existed; "
        "plotting it against the experiment_id duplicate check instead",
        path,
    )
    frame = pd.read_csv(path)
    if "experiment_id" not in frame.columns:
        raise ValueError(
            f"{path} has neither planned_point_id nor experiment_id; "
            "there is no way to check it for duplicate points, so it cannot be plotted"
        )
    identities = frame["experiment_id"]
    # A null, empty or whitespace-only identity is not an identity: duplicate detection
    # would pass it over, so the rows it stands for cannot be checked at all.
    blank = identities.isna() | (identities.astype("string").str.strip() == "")
    if blank.any():
        raise ValueError(
            f"{path} contains {int(blank.sum())} row(s) with a blank experiment_id; "
            "those points cannot be checked for duplication, so it cannot be plotted"
        )
    duplicates = identities.duplicated()
    if duplicates.any():
        raise ValueError(f"{path} contains {int(duplicates.sum())} duplicate experiment_id rows")
    frame["success"] = frame["success"].astype(bool)
    return frame


def _successes(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["success"].astype(bool)].reset_index(drop=True)
