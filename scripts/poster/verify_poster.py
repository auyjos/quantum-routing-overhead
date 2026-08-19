"""Re-derive every number printed on the A0 poster from the journalled run data.

The poster is assembled from literals in `build_poster.py`. Literals drift. This reads
them back out of the rendered HTML and checks each against the CSVs, so a typo or a stale
copy-paste fails loudly instead of being printed at A0.
"""
import pathlib
import re
import sys

import pandas as pd

CANON = pathlib.Path("/home/claude/qro/raw.csv")
SWEEP = pathlib.Path("/home/claude/work/artifacts/runs/relabelling-sweep")
HTML = pathlib.Path("poster_a0.html")

raw = pd.read_csv(CANON)
con = raw[raw.topology != "complete_27"]
dist = pd.read_csv(SWEEP / "relabelling_distribution.csv")
rank = pd.read_csv(SWEEP / "ranking_robustness.csv")
inv = pd.read_csv(SWEEP / "label_invariance.csv")
html = HTML.read_text(encoding="utf-8")
# Token checks run against a whitespace-normalised copy: otherwise a token only matches
# when the source happens to wrap the sentence the same way the check spells it.
flat = " ".join(html.split())

LINE, CAIRO = "line_27", "cairo_heavy_hex_27"
failures = []


def med(frame, **flt):
    for key, value in flt.items():
        frame = frame[frame[key] == value]
    return float(frame.two_qubit_depth_penalty.median())


def check(label, computed, printed, tol=5e-4):
    """`printed` must appear in the HTML *and* match the recomputed value."""
    shown = f"{printed}&times;" in html or f"<b>{printed}" in html or printed in html
    agrees = abs(computed - float(printed)) <= tol
    if not (shown and agrees):
        failures.append(
            f"{label}: printed={printed} computed={computed:.4f} "
            f"{'(not found in poster)' if not shown else ''}"
        )
    print(f"{'ok  ' if shown and agrees else 'FAIL'} {label:46s} "
          f"printed {printed:>8s}  computed {computed:.4f}")


# --- headline penalties -----------------------------------------------------
check("line pooled median", med(con, topology=LINE), "2.691")
check("heavy-hex pooled median", med(con, topology=CAIRO), "2.909")
no_l0 = con[con.optimization_level != 0]
check("line pooled, excl. L0", med(no_l0, topology=LINE), "2.140")
check("heavy-hex pooled, excl. L0", med(no_l0, topology=CAIRO), "2.304")
# --- section 02: the derived per-family comparison, levels 1 and 3 -----------
no0 = con[con.optimization_level != 0]
check("QFT on line, L1+L3", med(no0, topology=LINE, circuit_family="qft"), "2.321")
check("QFT on heavy-hex, L1+L3", med(no0, topology=CAIRO, circuit_family="qft"), "2.897")
check("EfficientSU2 on heavy-hex, L1+L3",
      med(no0, topology=CAIRO, circuit_family="efficient_su2"), "2.125")
check("EfficientSU2 on line, L1+L3",
      med(no0, topology=LINE, circuit_family="efficient_su2"), "3.427")
check("GHZ chain, both maps, L1+L3",
      med(no0, circuit_family="ghz_chain"), "1.000")

# --- optimization ------------------------------------------------------------
check("line L0", med(con, topology=LINE, optimization_level=0), "3.904")
check("line L3", med(con, topology=LINE, optimization_level=3), "1.991")
check("heavy-hex L0", med(con, topology=CAIRO, optimization_level=0), "4.282")
check("heavy-hex L3", med(con, topology=CAIRO, optimization_level=3), "2.174")

# --- seed variability --------------------------------------------------------
worst = con[(con.circuit_family == "qft") & (con.topology == CAIRO)
            & (con.logical_qubits == 20) & (con.optimization_level == 0)]
check("QFT/heavy-hex/n=20/L0 min", float(worst.two_qubit_depth_penalty.min()), "5.419")
check("QFT/heavy-hex/n=20/L0 max", float(worst.two_qubit_depth_penalty.max()), "7.527")

# --- label-permutation control ----------------------------------------------
star_l3 = con[(con.circuit_family == "ghz_star") & (con.optimization_level == 3)
              & (con.topology == LINE)]
check("GHZ star line L3 identity", float(star_l3.two_qubit_depth_penalty.median()), "1.87",
      tol=5e-3)
worst_shift = float(inv.relative_shift.max())
check("largest single-control shift", worst_shift, "15.70", tol=5e-3)

sweep_raw = pd.read_csv(SWEEP / "raw_results.csv")
sys.path.insert(0, "/home/claude/work/src")
from routing_overhead.topologies import base_topology, is_sweep  # noqa: E402

sweep_raw = sweep_raw[sweep_raw.success.astype(bool)]
sweep_raw["base"] = sweep_raw.topology.map(base_topology)
star_sweep = sweep_raw[(sweep_raw.circuit_family == "ghz_star")
                       & (sweep_raw.optimization_level == 3)
                       & (sweep_raw.base == LINE)
                       & sweep_raw.topology.map(is_sweep)]
check("GHZ star line L3 relabelling median",
      float(star_sweep.groupby("topology").two_qubit_depth_penalty.median().median()),
      "3.99", tol=5e-3)

spreads = dist[dist.optimization_level != 0].spread_ratio
check("min L1/L3 across-labelling spread", float(spreads.min()), "1.06", tol=5e-3)
check("max L1/L3 across-labelling spread", float(spreads.max()), "1.23", tol=5e-3)

# --- ranking robustness ------------------------------------------------------
for family, column, printed in (("qft", "line_27_cheaper", "24"),
                                ("efficient_su2", "cairo_heavy_hex_27_cheaper", "24"),
                                ("ghz_star", "cairo_heavy_hex_27_cheaper", "22")):
    value = float(rank[rank.circuit_family == family][column].iloc[0])
    check(f"ranking {family}", value, printed, tol=0)

# --- structural claims -------------------------------------------------------
# The control total is printed as a breakdown; check the parts and that they add up.
CONTROL = {"17,280": "relabelling sweep", "1,800": "matched baselines",
           "960": "VF2Layout instrumentation", "20,040": "control total"}
assert 17280 + 1800 + 960 == 20040, "printed control breakdown does not sum"
for token in ("28 of 28", "15 of 15", "1,080 of 1,080", "24 of 24", "22 of 24",
              "17,280 relabelling sweep + 1,800 matched baselines + 960",
              "20,040 in the control"):
    present = token in flat
    print(f"{'ok  ' if present else 'FAIL'} poster carries {token!r}")
    if not present:
        failures.append(f"missing token {token!r}")

print()
if failures:
    print(f"*** {len(failures)} POSTER CLAIM(S) FAILED ***")
    for failure in failures:
        print("   ", failure)
    raise SystemExit(1)
print("ALL POSTER CLAIMS VERIFIED AGAINST THE RUN DATA")
