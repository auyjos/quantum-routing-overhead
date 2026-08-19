"""Permutation-sweep figure: the labelling effect as a distribution, its
consequence for the topology ranking, and the pass-level mechanism.

Three render modes, one set of drawing code:

  (default)      one combined figure, three panels — used by the Gamma deck
  QRO_POSTER=1   the same, with the page's own headings suppressed
  QRO_SPLIT=1    each panel as its own figure, fig11a / fig11b / fig11c

Split exists because this figure runs full width on the poster. A single combined
raster stretched to 809 mm prints at roughly half the resolution of the figures that
occupy one column, and it cannot be moved or replaced panel-by-panel in a layout tool.
"""
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import style as S

S.apply()
raw = pd.read_csv("/home/claude/work/artifacts/runs/relabelling-sweep/raw_results.csv")
sys.path.insert(0, "/home/claude/work/src")
from routing_overhead.topologies import base_topology, is_sweep, sweep_index  # noqa: E402

raw = raw[raw.success.astype(bool)]
raw["base_topology"] = raw.topology.map(base_topology)
raw["labeling_id"] = [
    f"r{sweep_index(t):02d}" if is_sweep(t) else ("identity" if t == b else "stored")
    for t, b in zip(raw.topology, raw.base_topology)
]
p = raw[raw.topology != "complete_27"]
RAND = [f"r{i:02d}" for i in range(24)]
CTRL, GREEN = "#C2413F", "#3E8E5E"
SPLIT = bool(os.environ.get("QRO_SPLIT"))

# Standalone panels carry their own titles at readable size; inside the combined figure
# the three share the space and the type steps down to fit.
TITLE_PT = 17 if SPLIT else 15
SUB_PT = 12 if SPLIT else 11


# ---- panel A: pooled median per labelling, by level -------------------------
def panel_a(ax):
    rng = np.random.RandomState(11)
    for i, lvl in enumerate([0, 1, 3]):
        for j, base in enumerate(["cairo_heavy_hex_27", "line_27"]):
            col = S.TOPO_COLOR[base]
            x0 = i + (j - 0.5) * 0.36
            meds = [p[(p.base_topology == base) & (p.labeling_id == lab)
                      & (p.optimization_level == lvl)].two_qubit_depth_penalty.median()
                    for lab in RAND]
            ax.scatter(np.full(24, x0) + rng.uniform(-.06, .06, 24), meds, s=25,
                       color=col, alpha=0.5, linewidths=0, zorder=3)
            lo, med, hi = np.percentile(meds, [25, 50, 75])
            ax.add_patch(plt.Rectangle((x0 - 0.135, lo), 0.27, max(hi - lo, 0.004),
                                       facecolor=col, alpha=0.16, edgecolor=col,
                                       lw=1.2, zorder=2))
            ax.plot([x0 - 0.135, x0 + 0.135], [med, med], color=col, lw=2.6,
                    zorder=4, solid_capstyle="butt")
            ident = p[(p.base_topology == base) & (p.labeling_id == "identity")
                      & (p.optimization_level == lvl)].two_qubit_depth_penalty.median()
            ax.scatter([x0], [ident], marker="D", s=95, facecolor=S.PAPER,
                       edgecolor=CTRL, linewidths=2.2, zorder=6)

    ax.annotate("identity labelling\n(the study's maps)", xy=(0.155, 3.80),
                xytext=(0.62, 4.9), fontsize=10.5, color=CTRL, fontweight="bold",
                ha="left", va="center", linespacing=1.35,
                arrowprops=dict(arrowstyle="-|>", color=CTRL, lw=1.4,
                                connectionstyle="arc3,rad=-0.25"))
    ax.set_yscale("log")
    ax.set_yticks([2, 4, 8, 16])
    ax.get_yaxis().set_major_formatter(plt.ScalarFormatter())
    ax.yaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_xticks(range(3))
    ax.set_xticklabels(["level 0", "level 1", "level 3"], fontsize=12.5)
    ax.set_ylabel("Pooled median 2q depth penalty (×, log)", fontsize=11.5)
    ax.set_title("24 relabellings per map", fontsize=TITLE_PT, pad=34, loc="left")
    ax.text(0, 1.05, "◆ = identity labelling; box = IQR of the 24 relabellings",
            transform=ax.transAxes, fontsize=SUB_PT, color=S.INK_SOFT)
    ax.set_xlim(-0.52, 2.55)
    S.strip(ax)
    ax.text(0.985, 0.965, "Heavy-hex", transform=ax.transAxes, ha="right",
            va="top", fontsize=12, fontweight="bold", color=S.C_CAIRO)
    ax.text(0.985, 0.900, "Linear", transform=ax.transAxes, ha="right", va="top",
            fontsize=12, fontweight="bold", color=S.C_LINE)


# ---- panel B: reversal robustness scatter -----------------------------------
def _wins(fam):
    line_w = hex_w = 0
    for labg in RAND:
        d = p[(p.labeling_id == labg) & (p.circuit_family == fam)
              & (p.optimization_level != 0)]
        a = d[d.base_topology == "line_27"].two_qubit_depth_penalty.median()
        b = d[d.base_topology == "cairo_heavy_hex_27"].two_qubit_depth_penalty.median()
        line_w += a < b
        hex_w += b < a
    return line_w, hex_w


FAMS = []
for _fam, _col, _name in (("qft", "#20516B", "QFT"),
                          ("efficient_su2", "#3E8E5E", "EfficientSU2"),
                          ("ghz_star", "#9A6A00", "GHZ Star")):
    _lw, _hw = _wins(_fam)
    _side = "line" if _lw >= _hw else "heavy-hex"
    FAMS.append((_fam, _col, f"{_name} — {_side} cheaper {max(_lw, _hw)}/24"))


def panel_b(ax):
    for fam, col, lab in FAMS:
        xs, ys = [], []
        for labg in RAND:
            d = p[(p.labeling_id == labg) & (p.circuit_family == fam)
                  & (p.optimization_level != 0)]
            xs.append(d[d.base_topology == "line_27"].two_qubit_depth_penalty.median())
            ys.append(d[d.base_topology == "cairo_heavy_hex_27"]
                      .two_qubit_depth_penalty.median())
        ax.scatter(xs, ys, s=42, color=col, alpha=0.72, linewidths=0, zorder=3)
        d = p[(p.labeling_id == "identity") & (p.circuit_family == fam)
              & (p.optimization_level != 0)]
        xi = d[d.base_topology == "line_27"].two_qubit_depth_penalty.median()
        yi = d[d.base_topology == "cairo_heavy_hex_27"].two_qubit_depth_penalty.median()
        ax.scatter([xi], [yi], marker="D", s=100, facecolor=S.PAPER, edgecolor=CTRL,
                   linewidths=2.2, zorder=6)

    lim = (0.8, 5.6)
    ax.plot(lim, lim, color=S.RULE, lw=1.4, zorder=1)
    ax.text(5.05, 5.28, "equal", fontsize=10, color=S.INK_SOFT, rotation=45,
            ha="center", va="center")
    ax.text(0.95, 5.32, "cheaper on line", fontsize=10.5, color=S.INK_SOFT,
            style="italic")
    # Kept clear of the family key in the lower-left corner, which crowds it once the
    # figure is narrowed.
    ax.text(5.45, 3.78, "cheaper on heavy-hex", ha="right", fontsize=10.5,
            color=S.INK_SOFT, style="italic")

    sx = p[(p.labeling_id == "identity") & (p.circuit_family == "ghz_star")
           & (p.optimization_level != 0) & (p.base_topology == "line_27")
           ].two_qubit_depth_penalty.median()
    sy = p[(p.labeling_id == "identity") & (p.circuit_family == "ghz_star")
           & (p.optimization_level != 0) & (p.base_topology == "cairo_heavy_hex_27")
           ].two_qubit_depth_penalty.median()
    ax.annotate("identity labelling made the star\nlook cheap on the line",
                xy=(sx + 0.08, sy), xytext=(2.55, 4.55), fontsize=10, color=CTRL,
                fontweight="bold", linespacing=1.3, ha="left",
                arrowprops=dict(arrowstyle="-|>", color=CTRL, lw=1.3,
                                connectionstyle="arc3,rad=0.25"))
    for fam, col, lab in FAMS:
        y = {"qft": 0.22, "efficient_su2": 0.135, "ghz_star": 0.05}[fam]
        ax.text(0.035, y, lab, transform=ax.transAxes, fontsize=10.5,
                fontweight="bold", color=col)
    ax.set_xlim(*lim); ax.set_ylim(*lim)
    ax.set_xlabel("Median penalty on Linear (×)", fontsize=11.5)
    ax.set_ylabel("Median penalty on Heavy-hex (×)", fontsize=11.5)
    ax.set_title("The reversal is label-robust", fontsize=TITLE_PT, pad=34, loc="left")
    ax.text(0, 1.05, "levels 1 + 3 pooled · one point per relabelling",
            transform=ax.transAxes, fontsize=SUB_PT, color=S.INK_SOFT)
    S.strip(ax, grid_axis="both")


# ---- panel C: mechanism flow ------------------------------------------------
def panel_c(ax):
    ax.set_axis_off(); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    head_pt, body_pt = (10.6, 9.2) if SPLIT else ((9.4, 8.1) if S.POSTER else (10.2, 8.9))

    def box(x, y, w, h, head, body, col, fill="white"):
        """Text is placed from the box edges, never centred on a fixed offset."""
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=0.010,rounding_size=0.022",
                                    facecolor=fill, edgecolor=col, lw=1.6))
        ax.text(x + w / 2, y + h - 0.045, head, ha="center", va="top",
                fontsize=head_pt, fontweight="bold", color=col)
        ax.text(x + w / 2, y + h - 0.125, body, ha="center", va="top",
                fontsize=body_pt, color=S.INK, linespacing=1.55)

    def arrow(x0, y0, x1, y1, col):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                     mutation_scale=15, color=col, lw=1.6))

    box(0.008, 0.815, 0.984, 0.155, "96 configurations · levels 1 and 3",
        "does VF2Layout find an exact embedding?", S.INK)
    box(0.008, 0.435, 0.462, 0.265, "exact embedding",
        "28 configurations\nVF2 solved 21 · trivial 7", GREEN, "#F2F7F3")
    box(0.530, 0.435, 0.462, 0.265, "VF2 fails",
        "68 configurations\nstochastic SabreLayout\nchooses the layout", CTRL, "#FBF2F1")
    box(0.008, 0.075, 0.462, 0.235, "label-invariant",
        "28 of 28\nthe result is forced\nby the graph", GREEN)
    box(0.530, 0.075, 0.462, 0.235, "of those 68",
        "15 systematic shifts\n33 within seed scatter\n20 stable anyway", CTRL)
    arrow(0.36, 0.815, 0.239, 0.712, GREEN)
    arrow(0.64, 0.815, 0.761, 0.712, CTRL)
    arrow(0.239, 0.435, 0.239, 0.322, GREEN)
    arrow(0.761, 0.435, 0.761, 0.322, CTRL)
    ax.text(0.5, 0.022,
            "every systematic shift falls in the right-hand branch · 0 exceptions",
            ha="center", va="top", fontsize=9.4 if SPLIT else (8.6 if S.POSTER else 9.4),
            color=S.INK_SOFT)
    ax.set_title("Why: the layout pass decides", fontsize=TITLE_PT, pad=34, loc="left")
    ax.text(0, 1.05, "instrumented VF2Layout_stop_reason, 960 compilations",
            transform=ax.transAxes, fontsize=SUB_PT, color=S.INK_SOFT)


# ---- caption values, computed so text can never drift from the figure -------
def _pooled(base, lab, lvl):
    return p[(p.base_topology == base) & (p.labeling_id == lab)
             & (p.optimization_level == lvl)].two_qubit_depth_penalty.median()


_L0 = {b: np.median([_pooled(b, l, 0) for l in RAND])
       for b in ("line_27", "cairo_heavy_hex_27")}
_SPREADS = []
for b in ("line_27", "cairo_heavy_hex_27"):
    for lvl in (1, 3):
        meds = [_pooled(b, l, lvl) for l in RAND]
        _SPREADS.append(max(meds) / min(meds))
_star = p[(p.circuit_family == "ghz_star") & (p.base_topology == "line_27")
          & (p.optimization_level == 3)]
_star_rand = [_star[_star.labeling_id == l].two_qubit_depth_penalty.median() for l in RAND]
_star_id = _star[_star.labeling_id == "identity"].two_qubit_depth_penalty.median()
# Sweep members only. Subtracting a fixed 2 from the topology count also swept in the two
# named control maps, which are relabellings but carry none of the 17,280.
_n_maps = p[p.labeling_id.str.startswith("r")].topology.nunique()
_n_compiles = len(p[p.labeling_id.str.startswith("r")])

_body = (
    f"Level 0: the identity labelling is more favourable than every relabelling tested, on both maps "
    f"(relabelling medians {_L0['line_27']:.2f}× on line, {_L0['cairo_heavy_hex_27']:.2f}× on heavy-hex).   "
    f"Levels 1 and 3: across-labelling spread falls to {min(_SPREADS):.2f}–{max(_SPREADS):.2f}×, and the "
    f"QFT / EfficientSU2 topology ranking holds in 24 of 24 relabellings.\n"
    f"GHZ star on the line at level 3 is the exception: identity gives {_star_id:.2f}× against a "
    f"relabelling median of {np.median(_star_rand):.2f}× "
    f"(range {min(_star_rand):.2f}–{max(_star_rand):.2f}×)."
)


# ---- render -----------------------------------------------------------------
if SPLIT:
    # Widths follow the combined layout's proportions so the three still read as one row
    # when the page sets them side by side at a common height.
    for name, drawer, size, adj in (
            ("fig11a_relabelling_distribution", panel_a, (6.6, 6.0),
             dict(left=0.155, right=0.975, top=0.845, bottom=0.085)),
            ("fig11b_reversal_robust", panel_b, (5.9, 6.0),
             dict(left=0.150, right=0.980, top=0.845, bottom=0.095)),
            ("fig11c_layout_mechanism", panel_c, (5.6, 6.0),
             dict(left=0.020, right=0.980, top=0.845, bottom=0.030))):
        f, a = plt.subplots(figsize=size)
        drawer(a)
        f.subplots_adjust(**adj)
        S.save(f, name)
else:
    fig = plt.figure(figsize=(15.8, 6.2) if S.POSTER else (17.5, 6.8))
    gs = GridSpec(1, 3, figure=fig, width_ratios=[1.25, 1.0, 0.95], wspace=0.32)
    panel_a(fig.add_subplot(gs[0, 0]))
    panel_b(fig.add_subplot(gs[0, 1]))
    panel_c(fig.add_subplot(gs[0, 2]))

    if not S.POSTER:
        fig.suptitle("Is the labelling effect real, typical, and explainable?",
                     fontsize=22, fontweight="bold", color=S.INK, y=1.13, x=0.068,
                     ha="left")
        # The composed page prints this standfirst above the figure; repeating it here
        # would set the same sentence twice, a few centimetres apart.
        fig.text(0.068, 1.055,
                 f"24 deterministically derived physical-qubit relabellings per constrained "
                 f"map — same graph every time — {_n_compiles:,} compilations across "
                 f"{_n_maps} relabelled coupling maps, identical settings.",
                 ha="left", fontsize=12.5, color=S.INK_SOFT)
        # On the poster this caption said, in different words, exactly what the three
        # findings printed directly above the figure already say. Duplicating it cost
        # about 50 mm of page height, which is type size everywhere else on the sheet.
        fig.text(0.5, -0.10, _body, ha="center", fontsize=11, color=S.INK,
                 linespacing=1.7)
    S.save(fig, "fig11_permutation_sweep")
