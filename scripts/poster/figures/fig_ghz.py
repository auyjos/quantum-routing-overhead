"""GHZ chain vs GHZ star: interaction shape against coupling shape.

Family per row, optimization level per column, with the interaction schematic in a
leading column. The poster variant drops the title and standfirst, which the composed
page supplies, and carries slightly larger type.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec
import style as S

S.apply()
raw = pd.read_csv("raw.csv")

LEVELS = [0, 1, 3]
FAMS = [("ghz_chain", "GHZ Chain", "nearest-neighbour\ninteractions"),
        ("ghz_star", "GHZ Star", "one hub touches\nevery other qubit")]


def draw_chain(ax, col=S.INK):
    xs = np.arange(5)
    ax.plot(xs, [0] * 5, color=col, lw=2.2, zorder=1)
    ax.scatter(xs, [0] * 5, s=170, facecolor="white", edgecolor=col,
               linewidth=2.2, zorder=2)
    ax.set_xlim(-0.8, 4.8); ax.set_ylim(-1.5, 1.5)


def draw_star(ax, col=S.INK):
    edges = [(0, 0, 0, 1), (0, 0, 0, -1), (0, 0, -1.35, 0), (0, 0, 1.35, 0)]
    for x0, y0, x1, y1 in edges:
        ax.plot([x0, x1], [y0, y1], color=col, lw=2.2, zorder=1)
    pts = np.array([[0, 0], [0, 1], [0, -1], [-1.35, 0], [1.35, 0]])
    ax.scatter(pts[:, 0], pts[:, 1], s=170, facecolor="white", edgecolor=col,
               linewidth=2.2, zorder=2)
    ax.scatter([0], [0], s=170, facecolor=col, edgecolor=col, linewidth=2.2,
               zorder=3)
    ax.set_xlim(-2.2, 2.2); ax.set_ylim(-1.7, 1.7)


DRAW = {"ghz_chain": draw_chain, "ghz_star": draw_star}


def series(ax, fam, lvl):
    for topo in S.TOPO_ORDER:
        sub = raw[(raw.circuit_family == fam) & (raw.topology == topo)
                  & (raw.optimization_level == lvl)]
        g = sub.groupby("logical_qubits").two_qubit_depth_penalty
        med = g.median().reindex(S.SIZES)
        q25 = g.quantile(.25).reindex(S.SIZES)
        q75 = g.quantile(.75).reindex(S.SIZES)
        col = S.TOPO_COLOR[topo]
        base = topo == "complete_27"
        if not base:
            ax.fill_between(S.SIZES, q25, q75, color=col, alpha=0.18, lw=0)
        ax.plot(S.SIZES, med, color=col, lw=1.8 if base else 2.7,
                linestyle=(0, (5, 3)) if base else "-",
                marker="" if base else "o", ms=5.2,
                markerfacecolor=S.PAPER, markeredgewidth=1.9, zorder=3)
    ax.set_ylim(0.55, 5.9)
    ax.set_xticks(S.SIZES)
    S.strip(ax)


fig = plt.figure(figsize=(15.3, 5.7) if S.POSTER else (16.5, 6.4))
gs = GridSpec(2, 5, figure=fig, width_ratios=[0.85, 1, 1, 1, 0.02],
              height_ratios=[1, 1], wspace=0.30,
              hspace=0.62 if S.POSTER else 0.42)
for r, (fam, label, blurb) in enumerate(FAMS):
    ax0 = fig.add_subplot(gs[r, 0])
    DRAW[fam](ax0)
    ax0.set_axis_off()
    ax0.set_title(label, fontsize=18 if S.POSTER else 17,
                  pad=6 if S.POSTER else 10)
    ax0.text(0.5, -0.02, blurb, transform=ax0.transAxes, ha="center",
             va="top", fontsize=11.5 if S.POSTER else 10.5, color=S.INK_SOFT)
    for c, lvl in enumerate(LEVELS):
        ax = fig.add_subplot(gs[r, c + 1])
        series(ax, fam, lvl)
        if r == 0:
            ax.set_title(f"optimization level {lvl}", fontsize=13 if S.POSTER else 12.5,
                         color=S.INK_SOFT, fontweight="bold", pad=9)
        if r == 1:
            ax.set_xlabel("Logical qubits", fontsize=11 if S.POSTER else 10.5)
        if c != 0:
            ax.tick_params(labelleft=False)
fig.supylabel("Two-qubit depth penalty  (× baseline)",
              fontsize=12.5 if S.POSTER else 11.5, x=0.062)
if not S.POSTER:
    fig.suptitle("Interaction Structure Matters", fontsize=23, fontweight="bold",
                 color=S.INK, y=1.10)
legend_y = 1.005 if not S.POSTER else 1.03

# One key for all panels: the three series are the same everywhere, so labelling
# them inside a single panel would imply the key belongs to that panel alone.
handles = [
    Line2D([], [], color=S.TOPO_COLOR[topo],
           lw=1.8 if topo == "complete_27" else 2.7,
           linestyle=(0, (5, 3)) if topo == "complete_27" else "-",
           marker="" if topo == "complete_27" else "o", ms=5.2,
           markerfacecolor=S.PAPER, markeredgewidth=1.9,
           label=S.TOPO_LABEL[topo] + (" — 1×" if topo == "complete_27" else ""))
    for topo in S.TOPO_ORDER
]
legend = fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
                    fontsize=13.5 if S.POSTER else 12.5, handlelength=2.4,
                    columnspacing=3.0, bbox_to_anchor=(0.5, legend_y))
for text in legend.get_texts():
    text.set_fontweight("bold")

if not S.POSTER:
    fig.text(0.5, 1.028,
             "Same logical task, same qubit count, same compiler settings — only the "
             "shape of the required interactions differs.",
             ha="center", fontsize=12.5, color=S.INK_SOFT)
S.save(fig, "fig4_ghz_chain_vs_star")
