"""SABRE seed variability, stratified by what is actually stochastic.

At level 0 the layout is deterministic (`TrivialLayout`), so seed spread is routing
stochasticity alone. At levels 1 and 3 `SabreLayout` is stochastic too. Pooling the
strata would report two different quantities under one heading, so each level gets its
own panel and its own worst-case selection.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import style as S

S.apply()
raw = pd.read_csv("/home/claude/qro/raw.csv")
con = raw[raw.topology != "complete_27"]

LEVELS = [0, 1, 3]
STOCHASTIC = {
    0: "deterministic layout · SabreSwap only",
    1: "SabreLayout + SabreSwap",
    3: "SabreLayout + SabreSwap",
}

# x is not shared: the worst configuration is chosen inside each level, so the n= tick
# labels differ from panel to panel.
fig, axes = plt.subplots(1, 3, sharey=True,
                         figsize=(17.2, 6.1) if S.POSTER else (17.0, 6.2))

for ax, lvl in zip(axes, LEVELS):
    level_rows = con[con.optimization_level == lvl]
    med = level_rows.groupby(
        ["circuit_family", "topology", "logical_qubits"]
    ).two_qubit_depth_penalty.median().reset_index()

    pos, labels, sublabels = [], [], []
    p = 0.0
    entries = []
    for fam in S.FAMILY_ORDER:
        for j, topo in enumerate(["cairo_heavy_hex_27", "line_27"]):
            sel = med[(med.circuit_family == fam) & (med.topology == topo)]
            best = sel.loc[sel.two_qubit_depth_penalty.idxmax()]
            n = int(best.logical_qubits)
            vals = level_rows[
                (level_rows.circuit_family == fam)
                & (level_rows.topology == topo)
                & (level_rows.logical_qubits == n)
            ].two_qubit_depth_penalty.values
            entries.append((p + j * 0.60, topo, n, vals))
            pos.append(p + j * 0.60)
            sublabels.append(f"n={n}")
        labels.append((p + 0.30, S.FAMILY_LABEL[fam]))
        p += 2.05

    for x, topo, n, v in entries:
        col = S.TOPO_COLOR[topo]
        lo, q1, m, q3, hi = (v.min(), np.percentile(v, 25), np.median(v),
                             np.percentile(v, 75), v.max())
        ax.plot([x, x], [lo, hi], color=col, lw=1.6, alpha=0.65, zorder=2)
        for y in (lo, hi):
            ax.plot([x - 0.09, x + 0.09], [y, y], color=col, lw=1.6, alpha=0.65, zorder=2)
        ax.add_patch(plt.Rectangle((x - 0.16, q1), 0.32, max(q3 - q1, 0.012),
                                   facecolor=col, alpha=0.24, edgecolor=col,
                                   linewidth=1.3, zorder=3))
        ax.plot([x - 0.16, x + 0.16], [m, m], color=col, lw=2.8, zorder=5,
                solid_capstyle="butt")
        ax.scatter(np.full(len(v), x) + np.linspace(-0.05, 0.05, len(v)), v,
                   s=15, color=col, alpha=0.75, zorder=4, linewidths=0)
        if hi > lo:
            ax.annotate(f"{hi - lo:.2f}", (x, hi), xytext=(0, 7),
                        textcoords="offset points", ha="center", fontsize=8.5,
                        color=col, fontweight="bold")

    ax.set_xticks(pos)
    ax.set_xticklabels(sublabels, fontsize=8.5, color=S.INK_SOFT,
                       family="DejaVu Sans Mono")
    for x, lab in labels:
        ax.annotate(lab, (x, 0), xycoords=("data", "axes fraction"),
                    xytext=(0, -34), textcoords="offset points", ha="center",
                    fontsize=11 if S.POSTER else 11.5, fontweight="bold", color=S.INK,
                    annotation_clip=False)
    ax.axhline(1.0, color=S.C_COMPLETE, lw=1.5, linestyle=(0, (5, 3)), zorder=0)
    ax.set_title(f"optimization level {lvl}", fontsize=15, pad=34, loc="left")
    ax.text(0, 1.045, STOCHASTIC[lvl], transform=ax.transAxes, fontsize=10.5,
            color=S.INK_SOFT)
    ax.set_ylim(0.6, 8.4)
    S.strip(ax)

axes[0].set_ylabel("Two-qubit depth penalty  (× baseline)",
                   fontsize=12.5 if S.POSTER else 12)
# Shared key: both series appear in every panel.
handles = [
    Patch(facecolor=S.TOPO_COLOR[t], alpha=0.35, edgecolor=S.TOPO_COLOR[t],
          linewidth=1.4, label=S.TOPO_LABEL[t])
    for t in ("cairo_heavy_hex_27", "line_27")
] + [Line2D([], [], color=S.C_COMPLETE, lw=1.5, linestyle=(0, (5, 3)),
            label="Complete — 1×")]
legend = fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
                    fontsize=12, handlelength=2.2, columnspacing=3.0,
                    bbox_to_anchor=(0.5, 1.055 if not S.POSTER else 1.10))
for text in legend.get_texts():
    text.set_fontweight("bold")

# stratum statistics, computed from the same frame
stats = []
for lvl in LEVELS:
    g = con[con.optimization_level == lvl].groupby(
        ["circuit_family", "logical_qubits", "topology"]
    ).two_qubit_depth_penalty.agg(["min", "max", "median"])
    zero = float((g["max"] == g["min"]).mean())
    rel = float((g["max"] / g["min"]).median())
    stats.append(f"L{lvl}: {100*zero:.0f}% of configurations show no seed spread, "
                 f"median max/min {rel:.3f}×")

if not S.POSTER:
    fig.suptitle("SABRE Seed Variability, Stratified by Stochastic Source",
                 fontsize=21, fontweight="bold", color=S.INK, y=1.165, x=0.075, ha="left")
    fig.text(0.075, 1.10,
             "Worst configuration per circuit family and map, selected independently within each level · "
             "five fixed seeds (11, 22, 33, 44, 55) · whiskers min/max, box IQR, rule median",
             ha="left", fontsize=11.5, color=S.INK_SOFT)
tail = ("Level 0 carries the larger relative dispersion despite its deterministic layout "
        "(Mann-Whitney p = 2.6e-06, and the gap survives normalising by median penalty). "
        "Within levels 1 and 3, a median penalty of exactly 1.000× implies zero seed "
        "spread, 28 of 28.")
caption = "   ·   ".join(stats) + ".\n" + tail
if S.POSTER:
    # Rewrapped to the panel width: one long line would widen the tightened bounding box
    # past the axes, and the page then prints the whole figure smaller to fit that margin.
    import textwrap
    caption = "\n".join("\n".join(textwrap.wrap(part, 196)) or part
                        for part in caption.split("\n"))
# va="top" in poster mode: a baseline-anchored multi-line block grows upward into the
# family labels sitting just under the axes.
fig.text(0.5, -0.15 if not S.POSTER else -0.02, caption, ha="center",
         va="baseline" if not S.POSTER else "top",
         fontsize=10.5 if not S.POSTER else 11.5, color=S.INK, linespacing=1.7)
S.save(fig, "fig6_seed_variability")
