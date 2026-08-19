"""Method explainer: what is measured, what is held fixed, and what the control does.

Not a poster figure — a teaching diagram for talking through the study. Nothing here is
a result; every number that appears is a design parameter, not a measurement.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import style as S

S.apply()
CTRL, GREEN = "#C2413F", "#3E8E5E"

fig = plt.figure(figsize=(16.4, 10.6))
gs = GridSpec(3, 2, figure=fig, height_ratios=[1.28, 0.40, 1.12],
              width_ratios=[1, 1], hspace=0.42, wspace=0.13,
              left=0.035, right=0.968, top=0.848, bottom=0.035)


def panel(cell, number, title, subtitle):
    ax = fig.add_subplot(cell)
    ax.set_axis_off(); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.text(0, 1.10, number, transform=ax.transAxes, fontsize=13,
            fontweight="bold", color=CTRL, family="DejaVu Sans Mono")
    ax.text(0.035, 1.10, title, transform=ax.transAxes, fontsize=17,
            fontweight="bold", color=S.INK)
    ax.text(0.035, 1.015, subtitle, transform=ax.transAxes, fontsize=11.5,
            color=S.INK_SOFT)
    return ax


def box(ax, x, y, w, h, edge, fill="white", lw=1.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.008,rounding_size=0.03",
                                facecolor=fill, edgecolor=edge, lw=lw, zorder=2))


def arrow(ax, x0, y0, x1, y1, col=S.INK_SOFT, lw=1.7):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                 mutation_scale=15, color=col, lw=lw, zorder=3))


# ---------------------------------------------------------------- 1. the ratio
a = panel(gs[0, 0], "01", "What is measured",
          "one number per compilation, and it is a ratio — never a raw depth")

a.text(0.5, 0.945, "the same logical circuit, compiled twice", ha="center",
       fontsize=12.5, color=S.INK, fontweight="bold")

box(a, 0.02, 0.615, 0.45, 0.30, S.C_COMPLETE, "#F4F5F6")
a.text(0.245, 0.875, "complete connectivity", ha="center", fontsize=12.5,
       fontweight="bold", color=S.C_COMPLETE)
a.text(0.245, 0.805, "every qubit pair may interact\n351 couplings, diameter 1\nno routing is ever required",
       ha="center", va="top", fontsize=10.5, color=S.INK, linespacing=1.5)

box(a, 0.53, 0.615, 0.45, 0.30, S.C_CAIRO, "#F1F8F9")
a.text(0.755, 0.875, "constrained map", ha="center", fontsize=12.5,
       fontweight="bold", color=S.C_CAIRO)
a.text(0.755, 0.805, "heavy-hex 28 couplings, diam. 12\nline 26 couplings, diam. 26\nSWAPs must move qubits together",
       ha="center", va="top", fontsize=10.5, color=S.INK, linespacing=1.5)

arrow(a, 0.245, 0.600, 0.245, 0.520)
arrow(a, 0.755, 0.600, 0.755, 0.520)
a.text(0.245, 0.455, "two-qubit depth\n(the denominator)", ha="center", va="center",
       fontsize=10.5, color=S.INK_SOFT, linespacing=1.45)
a.text(0.755, 0.455, "two-qubit depth\n(the numerator)", ha="center", va="center",
       fontsize=10.5, color=S.INK_SOFT, linespacing=1.45)

box(a, 0.06, 0.145, 0.88, 0.19, S.INK, "#FFFFFF", lw=2.0)
a.text(0.5, 0.285, "two-qubit depth penalty", ha="center", va="center",
       fontsize=12.5, fontweight="bold", color=S.INK)
a.text(0.5, 0.200, "constrained two-qubit depth   ÷   matched complete-connectivity depth",
       ha="center", va="center", fontsize=12, color=S.INK)
a.text(0.5, 0.070, "1.000× means connectivity cost nothing at all",
       ha="center", va="center", fontsize=10.5, color=S.INK_SOFT, style="italic")


# ------------------------------------------------------- 2. what is held fixed
b = panel(gs[0, 1], "02", "What is varied, and what is not",
          "one independent variable; everything else is pinned so the ratio is a matched pair")

b.text(0.01, 0.965, "VARIED", fontsize=11.5, fontweight="bold", color=CTRL)
box(b, 0.0, 0.755, 1.0, 0.17, CTRL, "#FBF2F1")
b.text(0.5, 0.882, "hardware connectivity  —  and nothing else", ha="center",
       va="center", fontsize=13, fontweight="bold", color=CTRL)
b.text(0.5, 0.800, "complete   ·   heavy-hex (Cairo, 27 qubits)   ·   linear (27 qubits)",
       ha="center", va="center", fontsize=11, color=S.INK)

b.text(0.01, 0.690, "HELD FIXED across every comparison", fontsize=11.5,
       fontweight="bold", color=S.INK)
FIXED = [
    ("circuit instance", "identical, verified by circuit hash"),
    ("physical qubit count", "27 everywhere — sparsity is not size"),
    ("basis gates", "rz, sx, x, cx"),
    ("optimization level", "compared only against itself"),
    ("transpiler seed", "same seed on both sides of the ratio"),
]
for i, (k, v) in enumerate(FIXED):
    y = 0.600 - i * 0.088
    b.plot([0.02], [y], marker="o", ms=6, color=S.INK, zorder=4)
    b.text(0.055, y, k, va="center", fontsize=11.5, fontweight="bold", color=S.INK)
    b.text(0.40, y, v, va="center", fontsize=11, color=S.INK_SOFT)

box(b, 0.0, 0.020, 1.0, 0.135, S.RULE, "#FFFFFF", lw=1.2)
b.text(0.5, 0.120, "4 circuit families  ×  6 sizes (4–24 logical)  ×  3 topologies",
       ha="center", va="center", fontsize=11.5, color=S.INK)
b.text(0.5, 0.055, "×  3 optimization levels  ×  5 seeds   =   1,080 compilations",
       ha="center", va="center", fontsize=11.5, fontweight="bold", color=S.INK)


# ------------------------------------------------------------ 3. the four maps
c = fig.add_subplot(gs[1, :])
c.set_axis_off(); c.set_xlim(0, 1); c.set_ylim(0, 1)
c.text(0.0, 0.92, "03", transform=c.transAxes, fontsize=13, fontweight="bold",
       color=CTRL, family="DejaVu Sans Mono")
c.text(0.018, 0.92, "The question the control had to answer", fontsize=17,
       fontweight="bold", color=S.INK)
c.text(0.018, 0.70,
       "A coupling map is a graph. But the compiler does not see a graph — it sees a graph "
       "whose vertices carry integer names, and the circuit's qubits carry integer names too.\n"
       "If those names happen to line up, the compiler's job is easy for a reason that has "
       "nothing to do with connectivity. So: does the measured effect survive renaming?",
       fontsize=12.5, color=S.INK, linespacing=1.75, va="top")


# ------------------------------------------------------------ 4. the control
d = panel(gs[2, :], "04", "The control, and what it decides",
          "24 relabellings of each constrained map · same edges, same degrees, same diameter, "
          "same mean path length · only the integer names change")

xs = np.array([0.03, 0.075, 0.12, 0.165, 0.21])
for row, (lab, names, col) in enumerate((
        ("this study's labelling", ["0", "1", "2", "3", "4"], S.INK),
        ("one relabelling of it", ["3", "0", "4", "1", "2"], CTRL))):
    y = 0.80 - row * 0.30
    d.plot(xs, [y] * 5, color=col, lw=2.0, zorder=2)
    d.scatter(xs, [y] * 5, s=330, facecolor="white", edgecolor=col, lw=2.0, zorder=3)
    for x, n in zip(xs, names):
        d.text(x, y, n, ha="center", va="center", fontsize=10.5, color=col,
               fontweight="bold", zorder=4)
    d.text(0.245, y, lab, va="center", fontsize=12, color=col, fontweight="bold")

d.text(0.03, 0.36, "identical graph — recompile everything, and compare",
       fontsize=11.5, color=S.INK_SOFT, style="italic")

arrow(d, 0.44, 0.60, 0.50, 0.60, S.INK)

box(d, 0.52, 0.545, 0.225, 0.415, GREEN, "#F2F7F3")
d.text(0.6325, 0.885, "result unchanged", ha="center", va="center", fontsize=12.5,
       fontweight="bold", color=GREEN)
d.text(0.6325, 0.795, "the number was\nabout connectivity", ha="center", va="center",
       fontsize=10.5, color=S.INK, linespacing=1.5)
d.text(0.6325, 0.660, "levels 1 and 3:\nspread 1.06–1.23×", ha="center", va="center",
       fontsize=10.5, color=GREEN, fontweight="bold", linespacing=1.5)

box(d, 0.765, 0.545, 0.225, 0.415, CTRL, "#FBF2F1")
d.text(0.8775, 0.885, "result moves", ha="center", va="center", fontsize=12.5,
       fontweight="bold", color=CTRL)
d.text(0.8775, 0.795, "the number was\nabout labelling", ha="center", va="center",
       fontsize=10.5, color=S.INK, linespacing=1.5)
d.text(0.8775, 0.660, "level 0:\nup to 15.70×", ha="center", va="center",
       fontsize=10.5, color=CTRL, fontweight="bold", linespacing=1.5)

box(d, 0.52, 0.055, 0.47, 0.40, S.INK, "#FFFFFF", lw=2.0)
d.text(0.7550, 0.385, "and the split is not a judgement call",
       ha="center", va="center", fontsize=12.5, fontweight="bold", color=S.INK)
d.text(0.7550, 0.250, "VF2Layout finds an exact embedding  →  label-invariant, 28 of 28",
       ha="center", va="center", fontsize=11, color=S.INK)
d.text(0.7550, 0.130, "VF2Layout fails, SabreLayout guesses  →  every systematic shift, 15 of 15",
       ha="center", va="center", fontsize=11, color=S.INK)

d.text(0.03, 0.16,
       "Level 0 pins the layout to the identity permutation,\n"
       "so it is the stratum where names matter most.\n"
       "Every topology claim on the poster excludes it.",
       fontsize=11, color=S.INK, linespacing=1.7, va="center")

fig.suptitle("How the study works", fontsize=25, fontweight="bold", color=S.INK,
             x=0.035, y=0.988, ha="left")
fig.text(0.035, 0.928,
         "A compiler benchmark, not a hardware experiment. It measures what the Qiskit "
         "transpiler produces under different connectivity constraints — and then checks "
         "whether that measurement was about connectivity at all.",
         fontsize=13, color=S.INK_SOFT, ha="left")

S.save(fig, "fig14_method_explainer")
