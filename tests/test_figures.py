"""Stage 4 tests for the poster figure set."""

import shutil

import matplotlib.pyplot as plt
import matplotlib.text as mtext
import pandas as pd
import pytest

from routing_overhead.aggregation import aggregate_run
from routing_overhead.config import ExperimentConfig
from routing_overhead.experiments import prepare_run_directory, read_raw_results, run_grid
from routing_overhead.plotting import (
    COUNT_METRIC,
    FIGURE_NAMES,
    PRIMARY_METRIC,
    plot_run,
    pooled_compile_times,
)

# A miniature core grid: both GHZ families, a constrained topology, several levels and
# seeds, so every poster figure has the data shape it needs.
CONFIG = ExperimentConfig(
    physical_qubits=27,
    logical_qubits=(4, 6),
    circuit_families=("ghz_chain", "ghz_star"),
    topologies=("complete_27", "line_27"),
    optimization_levels=(0, 1, 3),
    transpiler_seeds=(11, 22),
    basis_gates=("rz", "sx", "x", "cx"),
)


@pytest.fixture(scope="module")
def core_run(tmp_path_factory):
    run_dir = prepare_run_directory(CONFIG, tmp_path_factory.mktemp("core"), "canonical")
    run_grid(CONFIG, run_dir)
    aggregate_run(run_dir)
    return run_dir


def _repeat(core_run, name, scale=1.0, edit=None):
    """Copy the canonical run into a timing repeat with different compile times."""
    repeat_dir = core_run.parent / name
    if repeat_dir.exists():
        shutil.rmtree(repeat_dir)
    shutil.copytree(core_run, repeat_dir)
    frame = pd.read_csv(repeat_dir / "raw_results.csv")
    frame["run_id"] = name
    frame["compile_time_seconds"] = frame["compile_time_seconds"] * scale
    if edit is not None:
        frame = edit(frame)
    frame.to_csv(repeat_dir / "raw_results.csv", index=False, na_rep="")
    return repeat_dir


@pytest.fixture(scope="module")
def timing_repeats(core_run):
    return [_repeat(core_run, "repeat-2", 1.1), _repeat(core_run, "repeat-3", 0.9)]


def test_plot_run_writes_every_poster_figure_as_raster_and_vector(core_run, timing_repeats):
    figures = plot_run(core_run, timing_runs=timing_repeats)

    written = {path.name for path in figures}
    expected = {f"{name}{suffix}" for name in FIGURE_NAMES for suffix in (".png", ".svg")}
    assert written == expected
    assert len(figures) == 2 * len(FIGURE_NAMES) == 12
    for path in figures:
        assert path.is_file()
        assert path.stat().st_size > 0
        assert path.parent == core_run / "figures"


def test_timing_figure_is_skipped_when_no_repeat_runs_are_given(core_run):
    figures = plot_run(core_run)

    names = {path.stem for path in figures}
    assert "optimization_quality_vs_time" not in names
    # Every other figure comes from the run directory alone.
    assert names == set(FIGURE_NAMES) - {"optimization_quality_vs_time"}


def test_pooled_compile_times_keeps_one_observation_per_point_per_process(core_run, timing_repeats):
    pooled = pooled_compile_times(core_run, timing_repeats)

    canonical = read_raw_results(core_run)
    canonical = canonical[canonical["success"]]
    assert len(pooled) == 3 * len(canonical)
    assert pooled.groupby("planned_point_id")["source_run"].nunique().eq(3).all()
    assert pooled["source_run"].nunique() == 3
    assert pooled["compile_time_seconds"].notna().all()


def test_pooled_compile_times_rejects_a_repeat_with_missing_points(core_run):
    short = _repeat(core_run, "repeat-short", edit=lambda frame: frame.iloc[:-1])

    with pytest.raises(ValueError, match="planned point"):
        pooled_compile_times(core_run, [short])


def test_pooled_compile_times_rejects_a_repeat_with_different_routing_output(core_run):
    def bend(frame):
        frame.loc[0, "output_two_qubit_depth"] = frame.loc[0, "output_two_qubit_depth"] + 1
        return frame

    bent = _repeat(core_run, "repeat-bent", edit=bend)

    with pytest.raises(ValueError, match="output_two_qubit_depth"):
        pooled_compile_times(core_run, [bent])


def test_penalty_figures_plot_saved_summary_medians(core_run, monkeypatch):
    """Every line drawn must come from the saved summary table, not from fresh values."""
    summary = pd.read_parquet(core_run / "summary_results.parquet")
    saved = set(summary["median"].round(9))
    plotted = []
    real_plot = plt.Axes.plot

    def record(self, *args, **kwargs):
        if len(args) >= 2:
            plotted.extend(round(float(value), 9) for value in args[1])
        return real_plot(self, *args, **kwargs)

    monkeypatch.setattr(plt.Axes, "plot", record)
    plot_run(core_run)

    assert plotted
    assert set(plotted) <= saved


def test_penalty_axes_are_zero_based_and_clip_no_facet(core_run, monkeypatch):
    from routing_overhead import plotting

    captured = {}
    real_save = plotting._save

    def capture(figure, figures_dir, name):
        captured[name] = [axis.get_ylim() for axis in figure.axes]
        return real_save(figure, figures_dir, name)

    monkeypatch.setattr(plotting, "_save", capture)
    plot_run(core_run)

    summary = pd.read_parquet(core_run / "summary_results.parquet")
    penalties = summary[summary["metric"] == PRIMARY_METRIC]
    highest = float(penalties[["median", "q75"]].to_numpy().max())
    bottoms, tops = zip(*captured[PRIMARY_METRIC])
    assert set(bottoms) == {0.0}
    assert min(tops) >= highest


def test_seed_variability_boxplots_use_the_saved_per_seed_values(core_run, monkeypatch):
    raw = read_raw_results(core_run)
    saved = set(raw[PRIMARY_METRIC].dropna().astype(float).round(9))
    boxed = []
    real_boxplot = plt.Axes.boxplot

    def record(self, values, *args, **kwargs):
        boxed.extend(round(float(value), 9) for series in values for value in series)
        return real_boxplot(self, values, *args, **kwargs)

    monkeypatch.setattr(plt.Axes, "boxplot", record)
    plot_run(core_run)

    assert boxed
    assert set(boxed) <= saved


def test_topology_figure_is_skipped_without_saved_edge_lists(core_run, tmp_path):
    stripped = tmp_path / "no-edges"
    shutil.copytree(core_run, stripped)
    topologies = pd.read_parquet(stripped / "topology_metadata.parquet")
    topologies.drop(columns=["edge_list_json"]).to_parquet(
        stripped / "topology_metadata.parquet", index=False
    )

    names = {path.stem for path in plot_run(stripped)}

    assert "topology_comparison" not in names
    assert PRIMARY_METRIC in names


def _legacy_run(core_run, destination):
    """A copy whose raw journal predates the `planned_point_id` column."""
    shutil.copytree(core_run, destination)
    frame = pd.read_csv(destination / "raw_results.csv")
    frame.drop(columns=["planned_point_id"]).to_csv(
        destination / "raw_results.csv", index=False, na_rep=""
    )
    return destination


def test_plot_run_reads_a_run_collected_before_planned_point_id(core_run, tmp_path):
    legacy = _legacy_run(core_run, tmp_path / "legacy")

    names = {path.stem for path in plot_run(legacy)}

    # The figures that need the raw journal must still be drawn from it.
    assert "seed_variability" in names
    assert names == set(FIGURE_NAMES) - {"optimization_quality_vs_time"}


def test_plot_run_rejects_a_legacy_journal_with_duplicate_experiment_ids(core_run, tmp_path):
    """The fallback read loses the planned-point duplicate check; experiment_id replaces it."""
    legacy = _legacy_run(core_run, tmp_path / "legacy-duplicates")
    frame = pd.read_csv(legacy / "raw_results.csv")
    pd.concat([frame, frame.iloc[:1]], ignore_index=True).to_csv(
        legacy / "raw_results.csv", index=False, na_rep=""
    )

    with pytest.raises(ValueError, match="duplicate experiment_id"):
        plot_run(legacy)


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_plot_run_rejects_a_legacy_journal_with_a_blank_experiment_id(core_run, tmp_path, blank):
    """A blank identity cannot be duplicate-checked, so it must not reach the figures."""
    legacy = _legacy_run(core_run, tmp_path / f"legacy-blank-{blank!r}")
    frame = pd.read_csv(legacy / "raw_results.csv")
    frame.loc[0, "experiment_id"] = blank
    frame.to_csv(legacy / "raw_results.csv", index=False, na_rep="")

    with pytest.raises(ValueError, match="blank experiment_id"):
        plot_run(legacy)


def test_pooled_compile_times_rejects_a_repeat_without_planned_point_id(core_run, tmp_path):
    legacy = _legacy_run(core_run, tmp_path / "legacy-repeat")

    with pytest.raises(ValueError, match="planned_point_id"):
        pooled_compile_times(core_run, [legacy])


def _captured_figures(monkeypatch):
    from routing_overhead import plotting

    captured = {}
    real_save = plotting._save

    def capture(figure, figures_dir, name):
        captured[name] = figure
        return real_save(figure, figures_dir, name)

    monkeypatch.setattr(plotting, "_save", capture)
    return captured


def test_penalty_figures_replace_the_complete_series_with_one_baseline_line(core_run, monkeypatch):
    captured = _captured_figures(monkeypatch)
    plot_run(core_run)
    summary = pd.read_parquet(core_run / "summary_results.parquet")

    for metric in (PRIMARY_METRIC, COUNT_METRIC):
        figure = captured[metric]
        labels = [text.get_text() for legend in figure.legends for text in legend.get_texts()]
        assert not any("Complete" in label and "penalty" not in label for label in labels)
        assert sum("penalty = 1" in label for label in labels) == 1

        constrained = summary[
            (summary["metric"] == metric) & (summary["topology"] != "complete_27")
        ]
        families = sorted(constrained["circuit_family"].unique())
        assert len(figure.axes) == len(families)
        for axis, family in zip(figure.axes, families):
            series = constrained[constrained["circuit_family"] == family]
            expected = series.groupby(["topology", "optimization_level"]).ngroups
            # Every constrained median series survives, plus the single baseline line.
            assert len(axis.lines) == expected + 1


def test_timing_annotations_offset_line_and_heavy_hex_apart():
    from routing_overhead.plotting import TIMING_LABEL_OFFSETS

    line = TIMING_LABEL_OFFSETS["line_27"]
    cairo = TIMING_LABEL_OFFSETS["cairo_heavy_hex_27"]
    # Opposite horizontal directions: the two topologies overlap in time at every level
    # and their vertical order is not stable across levels.
    assert line[0] < 0 < cairo[0]
    assert abs(cairo[0] - line[0]) >= 30


def test_coincident_series_are_disclosed_in_the_figures(core_run, monkeypatch):
    """Exact overlap must be labelled instead of looking like omitted data."""
    captured = _captured_figures(monkeypatch)
    plot_run(core_run)

    for metric in (PRIMARY_METRIC, COUNT_METRIC):
        chain_axis = next(axis for axis in captured[metric].axes if axis.get_title() == "GHZ chain")
        disclosure = " ".join(text.get_text() for text in chain_axis.texts)
        assert "line L0 = L1 = L3" in disclosure

    for axis in captured["ghz_chain_vs_star"].axes:
        disclosure = " ".join(text.get_text() for text in axis.texts)
        assert "chain on line = complete baseline" in disclosure

    seed_disclosure = " ".join(
        text.get_text() for axis in captured["seed_variability"].axes for text in axis.texts
    )
    assert "all 2 seeds = 1.0" in seed_disclosure


def test_penalty_figures_disclose_heavy_hex_l1_l3_overlap(tmp_path, monkeypatch):
    """The core-data heavy-hex L1/L3 overlap must be labelled for both metrics."""
    from routing_overhead import plotting

    captured = _captured_figures(monkeypatch)
    rows = []
    for metric in (PRIMARY_METRIC, COUNT_METRIC):
        for level, medians in ((0, (2.0, 3.0)), (1, (1.5, 2.0)), (3, (1.5, 2.0))):
            for logical_qubits, median in zip((4, 8), medians):
                rows.append(
                    {
                        "metric": metric,
                        "topology": "cairo_heavy_hex_27",
                        "circuit_family": "ghz_chain",
                        "optimization_level": level,
                        "logical_qubits": logical_qubits,
                        "median": median,
                        "q25": median,
                        "q75": median,
                    }
                )

    summary = pd.DataFrame(rows)
    for metric in (PRIMARY_METRIC, COUNT_METRIC):
        plotting._penalty_figure(summary, metric, tmp_path)
        disclosure = " ".join(text.get_text() for text in captured[metric].axes[0].texts)
        assert "heavy-hex L1 = L3" in disclosure


def test_source_figures_have_no_microtype(core_run, timing_repeats, monkeypatch):
    """Visible source-chart text must be at least 15 points before poster placement."""
    captured = _captured_figures(monkeypatch)
    plot_run(core_run, timing_runs=timing_repeats)

    for name, figure in captured.items():
        visible = [
            text.get_fontsize()
            for text in figure.findobj(match=mtext.Text)
            if text.get_visible() and text.get_text().strip()
        ]
        assert visible, name
        assert min(visible) >= 15, (name, min(visible))


def test_topology_figure_discloses_saved_graph_metrics(core_run, monkeypatch):
    """The topology comparison must expose the saved path and degree summaries."""
    captured = _captured_figures(monkeypatch)
    plot_run(core_run)

    figure = captured["topology_comparison"]
    titles = " ".join(axis.get_title() for axis in figure.axes)
    assert "mean degree" in titles
    assert "mean path" in titles
    assert "all maps connected" in " ".join(text.get_text() for text in figure.texts).lower()


def test_plot_run_requires_aggregation_first(tmp_path):
    run_dir = prepare_run_directory(CONFIG, tmp_path, "unaggregated")
    with pytest.raises(FileNotFoundError, match="summary_results.parquet"):
        plot_run(run_dir)
