"""Shared design system for the routing-overhead poster figures."""
import os

import matplotlib as mpl
import matplotlib.pyplot as plt

# Poster mode: the composed A0 page supplies its own section headings, so a figure that
# also carries a suptitle prints the same words twice and spends vertical space doing it.
POSTER = bool(os.environ.get("QRO_POSTER"))

# --- palette -------------------------------------------------------------
INK      = "#141B2D"   # dark navy, primary text
INK_SOFT = "#59617A"   # secondary text
RULE     = "#D8DBE4"   # hairline rules / gridlines
PAPER    = "#FBFBF9"   # warm off-white background

# topology colours -- FIXED, never remapped between figures
C_COMPLETE = "#7A828F"   # neutral gray  -- idealised baseline
C_CAIRO    = "#0E8C9E"   # cyan / teal   -- heavy-hex, hardware-representative
C_LINE     = "#7A3FD4"   # violet        -- linear, restrictive

TOPO_COLOR = {
    "complete_27": C_COMPLETE,
    "cairo_heavy_hex_27": C_CAIRO,
    "line_27": C_LINE,
}
TOPO_LABEL = {
    "complete_27": "Complete",
    "cairo_heavy_hex_27": "Heavy-hex",
    "line_27": "Linear",
}
TOPO_ORDER = ["complete_27", "cairo_heavy_hex_27", "line_27"]

FAMILY_LABEL = {
    "qft": "QFT",
    "ghz_chain": "GHZ Chain",
    "ghz_star": "GHZ Star",
    "efficient_su2": "EfficientSU2",
}
FAMILY_ORDER = ["qft", "ghz_chain", "ghz_star", "efficient_su2"]
SIZES = [4, 8, 12, 16, 20, 24]


def apply():
    mpl.rcParams.update({
        "figure.facecolor": PAPER,
        "axes.facecolor": PAPER,
        "savefig.facecolor": PAPER,
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.edgecolor": RULE,
        "axes.linewidth": 0.9,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.labelsize": 11,
        "axes.grid": True,
        "grid.color": RULE,
        "grid.linewidth": 0.7,
        "grid.alpha": 0.7,
        "xtick.color": INK_SOFT,
        "ytick.color": INK_SOFT,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
    })


def strip(ax, left=True, bottom=True, grid_axis="y"):
    """Thin axes: no top/right spines, single-axis gridlines."""
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_visible(left)
    ax.spines["bottom"].set_visible(bottom)
    ax.spines["left"].set_color(RULE)
    ax.spines["bottom"].set_color(RULE)
    ax.set_axisbelow(True)
    ax.grid(False)
    if grid_axis:
        ax.grid(True, axis=grid_axis, color=RULE, linewidth=0.7, alpha=0.8)


def save(fig, name, outdir="figs"):
    import os
    os.makedirs(outdir, exist_ok=True)
    for ext, dpi in (("png", 220),):
        fig.savefig(f"{outdir}/{name}.{ext}", dpi=dpi, bbox_inches="tight",
                    pad_inches=0.28, facecolor=PAPER)
    fig.savefig(f"{outdir}/{name}.svg", bbox_inches="tight",
                pad_inches=0.28, facecolor=PAPER)
    plt.close(fig)
    print("wrote", name)
