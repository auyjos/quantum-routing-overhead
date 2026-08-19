"""Seed variability, shown on four configurations instead of twenty-four.

The earlier version plotted every family on every map at every level: twenty-four tiny
box plots, none of them readable at poster distance. The claim only needs four rows —
the worst spread in the study, the same configuration after optimization, a second
family for corroboration, and one configuration with no spread at all.

Every value is read from the run data; nothing here is a literal.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import style as S

S.apply()
raw = pd.read_csv("raw.csv")
con = raw[raw.topology != "complete_27"]

CAIRO, LINE = "cairo_heavy_hex_27", "line_27"
# (family, topology, n, level, why this row is here)
ROWS = [
    ("qft", CAIRO, 20, 0, "widest spread in the study"),
    ("qft", CAIRO, 20, 3, "same configuration, optimization level 3"),
    ("efficient_su2", CAIRO, 16, 0, "a second family, same pattern"),
    ("ghz_chain", LINE, 24, 3, "no spread at all — the graph forces it"),
]


def seeds(fam, topo, n, lvl):
    sel = con[(con.circuit_family == fam) & (con.topology == topo)
              & (con.logical_qubits == n) & (con.optimization_level == lvl)]
    return np.sort(sel.two_qubit_depth_penalty.values)


fig, ax = plt.subplots(figsize=(16.2, 4.4) if S.POSTER else (14.5, 4.8))
fig.subplots_adjust(left=0.335, right=0.985, top=0.86, bottom=0.19)

xmax = 0.0
for i, (fam, topo, n, lvl, why) in enumerate(ROWS):
    y = len(ROWS) - 1 - i
    v = seeds(fam, topo, n, lvl)
    col = S.TOPO_COLOR[topo]
    lo, hi, mid = v.min(), v.max(), np.median(v)
    xmax = max(xmax, hi)

    if hi > lo:
        ax.plot([lo, hi], [y, y], color=col, lw=6.5, alpha=0.22, zorder=1,
                solid_capstyle="round")
    ax.scatter(v, np.full(len(v), y), s=260, color=col, alpha=0.9,
               edgecolor=S.PAPER, linewidths=2.2, zorder=4)
    ax.plot([mid, mid], [y - 0.17, y + 0.17], color=col, lw=3.0, zorder=5,
            solid_capstyle="butt")

    span = (f"{lo:.3f}×  to  {hi:.3f}×" if hi > lo else f"{lo:.3f}×, all five seeds")
    ax.annotate(span, (hi, y), xytext=(26, 0), textcoords="offset points",
                ha="left", va="center", fontsize=15.5, fontweight="bold", color=col)

    name = (f"{S.FAMILY_LABEL[fam]}  ·  {S.TOPO_LABEL[topo]}")
    ax.annotate(name, (0, y), xycoords=("axes fraction", "data"),
                xytext=(-18, 11), textcoords="offset points", ha="right",
                va="center", fontsize=16, fontweight="bold", color=S.INK)
    ax.annotate(f"n = {n}  ·  level {lvl}   —   {why}", (0, y),
                xycoords=("axes fraction", "data"), xytext=(-18, -12),
                textcoords="offset points", ha="right", va="center",
                fontsize=12.5, color=S.INK_SOFT)

ax.axvline(1.0, color=S.C_COMPLETE, lw=1.8, linestyle=(0, (5, 3)), zorder=0)
ax.annotate("complete connectivity = 1×", (1.0, len(ROWS) - 0.42), xytext=(8, 0),
            textcoords="offset points", ha="left", va="center", fontsize=11.5,
            color=S.C_COMPLETE, fontweight="bold")
ax.set_ylim(-0.62, len(ROWS) - 0.38)
ax.set_xlim(0.6, xmax * 1.30)
ax.set_yticks([])
ax.set_xlabel("Two-qubit depth penalty  (× complete connectivity)", fontsize=14)
ax.tick_params(axis="x", labelsize=13)
S.strip(ax, left=False, grid_axis="x")

handles = [Line2D([], [], marker="o", linestyle="", markersize=13,
                  color=S.TOPO_COLOR[t], label=S.TOPO_LABEL[t])
           for t in (CAIRO, LINE)]
legend = fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False,
                    fontsize=15, handletextpad=0.5, columnspacing=3.4,
                    bbox_to_anchor=(0.66, 0.995))
for text in legend.get_texts():
    text.set_fontweight("bold")

if not S.POSTER:
    fig.suptitle("One Circuit, Five Seeds, Five Different Answers",
                 fontsize=22, fontweight="bold", color=S.INK, y=1.11, x=0.02, ha="left")
    fig.text(0.02, 1.04,
             "Each dot is one of the five fixed transpiler seeds (11, 22, 33, 44, 55); "
             "the rule is the median. Nothing else about the compilation changes.",
             ha="left", fontsize=12.5, color=S.INK_SOFT)
S.save(fig, "fig13_seed_focus")
