"""Primary results grid: penalty vs logical size, faceted by circuit family
(columns) and Qiskit optimization level (rows).

Each point is the median of the 5 fixed transpiler seeds for that exact
configuration; each band is the IQR of those same 5 seeds. Nothing is pooled
across optimization levels inside a panel.
"""
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import style as S

S.apply()
raw = pd.read_csv("raw.csv")

METRIC = sys.argv[1] if len(sys.argv) > 1 else "two_qubit_depth_penalty"
fname, title, ylab = {
    "two_qubit_depth_penalty": (
        "fig2_two_qubit_depth_penalty",
        "Two-Qubit Depth Penalty vs. Logical Qubit Count",
        "Two-qubit depth penalty  (× baseline)"),
    "two_qubit_count_penalty": (
        "fig3_two_qubit_count_penalty",
        "Two-Qubit Gate-Count Penalty vs. Logical Qubit Count",
        "Two-qubit count penalty  (× baseline)"),
}[METRIC]

LEVELS = [0, 1, 3]

# Level per row, family per column in both modes. The poster variant is wider and
# shorter: on a portrait page a section is a wide band, so a tall grid would have to be
# scaled down to fit and would lose more type size than the extra rows gain.
ROWS, COLS = LEVELS, S.FAMILY_ORDER
fig, axes = plt.subplots(3, 4, sharey=True, sharex=True,
                         figsize=(16.4, 7.8) if S.POSTER else (17.5, 11.4))

ymax = 0.0
for r, lvl in enumerate(ROWS):
    for c, fam in enumerate(COLS):
        ax = axes[r, c]
        for topo in S.TOPO_ORDER:
            sub = raw[(raw.circuit_family == fam) & (raw.topology == topo)
                      & (raw.optimization_level == lvl)]
            g = sub.groupby("logical_qubits")[METRIC]
            med = g.median().reindex(S.SIZES)
            q25 = g.quantile(0.25).reindex(S.SIZES)
            q75 = g.quantile(0.75).reindex(S.SIZES)
            col = S.TOPO_COLOR[topo]
            base = topo == "complete_27"
            if not base:
                ax.fill_between(S.SIZES, q25, q75, color=col, alpha=0.18,
                                linewidth=0)
            ax.plot(S.SIZES, med, color=col,
                    linewidth=1.9 if base else 2.7,
                    linestyle=(0, (5, 3)) if base else "-",
                    marker="" if base else "o", markersize=5.4,
                    markerfacecolor=S.PAPER, markeredgewidth=1.9, zorder=3)
            ymax = max(ymax, float(np.nanmax(q75.values)))

        if r == 0:
            ax.set_title(S.FAMILY_LABEL[fam], fontsize=17 if S.POSTER else 16,
                         pad=14)
        if r == len(ROWS) - 1:
            ax.set_xlabel("Logical qubits", fontsize=11.5)
        ax.set_xticks(S.SIZES)
        S.strip(ax)

    # Facet strip on the right edge, so the whole left gutter belongs to the one shared
    # y-axis label instead of being split between it and three row captions.
    axes[r, -1].annotate(f"optimization\nlevel {lvl}", xy=(1, 0.5),
                         xycoords="axes fraction", xytext=(18, 0),
                         textcoords="offset points", rotation=270,
                         ha="center", va="center", fontsize=14 if S.POSTER else 13.5,
                         fontweight="bold", color=S.INK, linespacing=1.4,
                         multialignment="center")

axes[0, 0].set_ylim(0.55, ymax * 1.08)
# The y axis is shared by every panel, so it is labelled once for the whole grid.
fig.supylabel(ylab, fontsize=13.5, x=0.012)

# One shared legend for all twelve panels. Labelling series inside the fourth panel
# reads as though the labels belong to that panel alone; the series are identical
# everywhere, so the key belongs to the figure, not to any one facet.
handles = [
    Line2D([], [], color=S.TOPO_COLOR[topo],
           linewidth=1.9 if topo == "complete_27" else 2.7,
           linestyle=(0, (5, 3)) if topo == "complete_27" else "-",
           marker="" if topo == "complete_27" else "o", markersize=5.4,
           markerfacecolor=S.PAPER, markeredgewidth=1.9,
           label=S.TOPO_LABEL[topo] + (" — 1× denominator" if topo == "complete_27" else ""))
    for topo in S.TOPO_ORDER
]
legend = fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
                    fontsize=13.5, handlelength=2.6, columnspacing=3.4,
                    bbox_to_anchor=(0.5, 0.928 if not S.POSTER else 0.985))
for text in legend.get_texts():
    text.set_fontweight("bold")

# In poster mode the composed page supplies the title and both caption lines, so the
# figure prints only the panels — otherwise the captions collide with the column headers.
if not S.POSTER:
    fig.suptitle(title, fontsize=23, fontweight="bold", color=S.INK, y=0.985)
    fig.text(0.5, 0.947,
             "penalty  =  constrained-topology value  ÷  matched complete-connectivity "
             "value  (same circuit, size, level, seed and basis)",
             ha="center", fontsize=12.5, color=S.INK_SOFT)
    fig.text(0.5, 0.925,
             "point = median of the 5 fixed transpiler seeds   ·   band = IQR of those 5 "
             "seeds   ·   Complete is the 1× denominator by construction",
             ha="center", fontsize=11.5, color=S.INK_SOFT)
fig.subplots_adjust(wspace=0.10, hspace=0.24,
                    top=0.828 if not S.POSTER else 0.876,
                    left=0.062 if not S.POSTER else 0.055,
                    right=0.958 if not S.POSTER else 0.962)
S.save(fig, fname)
