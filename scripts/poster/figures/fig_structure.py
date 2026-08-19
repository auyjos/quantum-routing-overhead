"""Derived comparison: interaction shape decides which topology is cheaper.

One panel replacing the earlier six-facet chain-vs-star grid. The facets repeated
what the primary results grid already shows; what they did not show directly is the
ordering itself, which is the actual claim. Levels 1 and 3 only — level 0 is excluded
everywhere a topology claim is made, because the relabelling control shows it measures
physical-qubit numbering rather than connectivity.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
import style as S

S.apply()
raw = pd.read_csv("raw.csv")
con = raw[(raw.topology != "complete_27") & (raw.optimization_level != 0)]
med = con.groupby(["circuit_family", "topology"]).two_qubit_depth_penalty.median()

CTRL = "#C2413F"
ROWS = ["qft", "efficient_su2", "ghz_chain", "ghz_star"]
SHAPE = {
    "qft": "every pair interacts",
    "efficient_su2": "ring of neighbours",
    "ghz_chain": "nearest neighbours only",
    "ghz_star": "one hub touches all",
}


# --- interaction-shape glyphs ------------------------------------------------
def glyph_qft(ax):
    xs = np.arange(5)
    for i in range(5):
        for j in range(i + 1, 5):
            r = (j - i) / 2
            t = np.linspace(0, np.pi, 40)
            ax.plot((i + j) / 2 + r * np.cos(t), r * 0.55 * np.sin(t),
                    color=S.INK, lw=0.9, alpha=0.55, zorder=1)
    ax.scatter(xs, [0] * 5, s=70, facecolor="white", edgecolor=S.INK, lw=1.8, zorder=2)
    ax.set_xlim(-0.9, 4.9); ax.set_ylim(-0.9, 1.5)


def glyph_ring(ax):
    t = np.linspace(0, 2 * np.pi, 7)[:-1] + np.pi / 6
    x, y = np.cos(t), np.sin(t)
    ax.plot(np.append(x, x[0]), np.append(y, y[0]), color=S.INK, lw=1.8, zorder=1)
    ax.scatter(x, y, s=70, facecolor="white", edgecolor=S.INK, lw=1.8, zorder=2)
    ax.set_xlim(-1.7, 1.7); ax.set_ylim(-1.5, 1.5)


def glyph_chain(ax):
    xs = np.arange(5)
    ax.plot(xs, [0] * 5, color=S.INK, lw=1.8, zorder=1)
    ax.scatter(xs, [0] * 5, s=70, facecolor="white", edgecolor=S.INK, lw=1.8, zorder=2)
    ax.set_xlim(-0.9, 4.9); ax.set_ylim(-1.2, 1.2)


def glyph_star(ax):
    for x1, y1 in ((0, 1), (0, -1), (-1.3, 0), (1.3, 0)):
        ax.plot([0, x1], [0, y1], color=S.INK, lw=1.8, zorder=1)
    pts = np.array([[0, 1], [0, -1], [-1.3, 0], [1.3, 0]])
    ax.scatter(pts[:, 0], pts[:, 1], s=70, facecolor="white", edgecolor=S.INK,
               lw=1.8, zorder=2)
    ax.scatter([0], [0], s=70, facecolor=S.INK, edgecolor=S.INK, lw=1.8, zorder=3)
    ax.set_xlim(-1.9, 1.9); ax.set_ylim(-1.5, 1.5)


GLYPH = {"qft": glyph_qft, "efficient_su2": glyph_ring,
         "ghz_chain": glyph_chain, "ghz_star": glyph_star}

BIG = S.POSTER
fig = plt.figure(figsize=(16.2, 4.9) if BIG else (14.5, 5.4))
# Three columns: the interaction glyph, the family name, then the chart. The name needs
# a column of its own -- anchoring it to the chart's left edge runs it over the glyph.
gs = GridSpec(len(ROWS), 3, figure=fig, width_ratios=[0.085, 0.30, 1],
              wspace=0.02, hspace=0.0,
              left=0.012, right=0.985, top=0.845, bottom=0.135)

main = fig.add_subplot(gs[:, 2])
XMAX = 3.85
for i, fam in enumerate(ROWS):
    y = len(ROWS) - 1 - i
    line = float(med[(fam, "line_27")])
    cairo = float(med[(fam, "cairo_heavy_hex_27")])
    cheap = "line_27" if line < cairo else ("cairo_heavy_hex_27" if cairo < line else None)

    ax = fig.add_subplot(gs[i, 0])
    GLYPH[fam](ax)
    ax.set_axis_off()

    lab = fig.add_subplot(gs[i, 1])
    lab.set_axis_off()
    lab.text(1.0, 0.60, S.FAMILY_LABEL[fam], ha="right", va="center",
             fontsize=18, fontweight="bold", color=S.INK, transform=lab.transAxes)
    lab.text(1.0, 0.34, SHAPE[fam], ha="right", va="center", fontsize=13,
             color=S.INK_SOFT, transform=lab.transAxes)

    tie = abs(line - cairo) < 1e-9
    main.plot([min(line, cairo), max(line, cairo)], [y, y], color=S.RULE, lw=3.4,
              zorder=1, solid_capstyle="round")
    for value, topo in ((line, "line_27"), (cairo, "cairo_heavy_hex_27")):
        col = S.TOPO_COLOR[topo]
        win = topo == cheap
        # Where the two maps tie exactly, one marker would sit invisibly under the
        # other and the row would read as a single-topology result.
        dy = 0.0 if not tie else (0.085 if topo == "line_27" else -0.085)
        main.scatter([value], [y + dy], s=330 if win else 250, color=col,
                     edgecolor=S.PAPER, linewidths=2.4, zorder=4)
        if not tie:
            main.annotate(f"{value:.3f}×", (value, y), xytext=(0, 20 if win else -30),
                          textcoords="offset points", ha="center",
                          fontsize=15 if win else 13.5, fontweight="bold", color=col)
    if tie:
        main.annotate(f"{line:.3f}×  on both maps", (line, y), xytext=(22, 0),
                      textcoords="offset points", ha="left", va="center",
                      fontsize=15, fontweight="bold", color=S.INK)

main.axvline(1.0, color=S.C_COMPLETE, lw=1.8, linestyle=(0, (5, 3)), zorder=0)
main.annotate("complete\nconnectivity = 1×", (1.0, len(ROWS) - 0.5),
              xytext=(7, 0), textcoords="offset points", ha="left", va="center",
              fontsize=11.5, color=S.C_COMPLETE, fontweight="bold", linespacing=1.35)

# The ordering reverses between the two dense families -- the point of the panel.
main.annotate("", xy=(3.62, 3), xytext=(3.62, 2),
              arrowprops=dict(arrowstyle="-", color=S.INK, lw=1.4))
for yy in (3, 2):
    main.plot([3.55, 3.62], [yy, yy], color=S.INK, lw=1.4)
main.annotate("the ordering\nreverses", (3.66, 2.5), ha="left", va="center",
              fontsize=13, fontweight="bold", color=S.INK, linespacing=1.35)

# Parked to the right of the star's own row: below the axis it collides with the ticks.
main.annotate("does not survive\nthe labelling control", (3.13, 0), ha="left",
              va="center", fontsize=13, fontweight="bold", color=CTRL, linespacing=1.35)

main.set_ylim(-0.62, len(ROWS) - 0.38)
main.set_xlim(0.72, XMAX)
main.set_yticks([])
main.set_xlabel("Median two-qubit depth penalty, levels 1 and 3  (× complete connectivity)",
                fontsize=14)
main.tick_params(axis="x", labelsize=13)
S.strip(main, left=False, grid_axis="x")

handles = [Line2D([], [], marker="o", linestyle="", markersize=13,
                  color=S.TOPO_COLOR[t], label=S.TOPO_LABEL[t])
           for t in ("cairo_heavy_hex_27", "line_27")]
legend = fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False,
                    fontsize=15, handletextpad=0.5, columnspacing=3.4,
                    bbox_to_anchor=(0.62, 0.995))
for text in legend.get_texts():
    text.set_fontweight("bold")

if not S.POSTER:
    fig.suptitle("Interaction Structure Decides Which Topology Is Cheaper",
                 fontsize=22, fontweight="bold", color=S.INK, y=1.10, x=0.02, ha="left")
    fig.text(0.02, 1.035,
             "Median over levels 1 and 3, all sizes and seeds · level 0 excluded: the "
             "relabelling control shows it measures qubit numbering, not connectivity.",
             ha="left", fontsize=12.5, color=S.INK_SOFT)
S.save(fig, "fig12_interaction_structure")
