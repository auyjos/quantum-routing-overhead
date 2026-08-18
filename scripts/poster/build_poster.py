"""Compose the single-page A0 portrait poster.

Figures are embedded as base64 so the HTML is self-contained and the render is
reproducible without path resolution at print time. Every size is expressed as a
multiple of `--k`, which `render_poster.py` binary-searches for the largest value that
still fits one A0 page — so the layout is fitted rather than hand-tuned, and stays
correct if a figure is swapped for one with a different aspect ratio.

One section per row. Each row pairs its figure with a sidebar carrying that section's
heading, its caption and the finding it supports, so the space either side of a
wide figure holds the argument instead of sitting empty — and the findings print at
poster size rather than being compressed into a block at the foot of the page.

Every numeric claim is copied from `poster/poster-content.md` and re-checked against the
journalled run data by `verify_poster.py`.
"""
import base64
import pathlib

# Poster variants have their suptitles suppressed (QRO_POSTER=1); the page supplies the
# headings. Falls back to the titled figure when no poster variant exists, e.g. the QR.
FIGS, FIGS_POSTER = pathlib.Path("figs"), pathlib.Path("figs_poster")
INK, INK_SOFT, RULE, PAPER = "#141B2D", "#59617A", "#D8DBE4", "#FBFBF9"
TEAL, VIOLET, FLAG = "#0E8C9E", "#7A3FD4", "#C2413F"

FIG_MM = 560          # figure column width at k = 1
SIDE_MM = 214         # sidebar width at k = 1


def b64(name):
    path = FIGS_POSTER / f"{name}.png"
    if not path.exists():
        path = FIGS / f"{name}.png"
    return base64.b64encode(path.read_bytes()).decode()


def img(name, width_mm=FIG_MM):
    return (f'<img class="fig" style="width:calc({width_mm}mm * var(--k))" '
            f'src="data:image/png;base64,{b64(name)}">')


STATS = [
    ("2.691&times; / 2.909&times;", "Pooled median two-qubit depth penalty, line / heavy-hex"),
    ("2.140&times; / 2.304&times;", "The same, excluding the level-0 stratum the control rules out"),
    ("1.000&times;", "GHZ chain on the line, and circular EfficientSU2 on heavy-hex at n = 12 and 20"),
    ("21 / {12,&nbsp;20}", "Heavy-hex longest simple path and cycle spectrum &mdash; forced by the graph"),
]

# (number, heading, caption, [(finding heading, finding body), ...], figure)
SECTIONS = [
    ("01", "Primary result &mdash; two-qubit depth penalty",
     "penalty = constrained-topology value &divide; matched complete-connectivity value "
     "&middot; point = median of the 5 fixed seeds, band = their IQR &middot; matching "
     "fixes family, size, circuit hash, level, seed and basis",
     [("Connectivity",
       "Constrained connectivity commonly raises two-qubit depth: median <b>2.691&times;</b> "
       "on the line and <b>2.909&times;</b> on heavy-hex, 360 compilations each. Excluding "
       "level 0, <b>2.140&times;</b> and <b>2.304&times;</b>."),
      ("Optimization",
       "Level 3 roughly halves the penalty against level 0 &mdash; <b>3.904&times; &rarr; "
       "1.991&times;</b> on the line, <b>4.282&times; &rarr; 2.174&times;</b> on heavy-hex "
       "&mdash; at about 5&times; the local compile time.")],
     "fig2_two_qubit_depth_penalty"),

    ("02", "Interaction structure matters",
     "same logical task, same qubit count, same compiler settings &mdash; only the shape "
     "of the required interactions differs",
     [("Circuit structure",
       "Interaction shape dominates. GHZ chain on the line stays at exactly "
       "<b>1.000&times;</b> at every size and level, while GHZ star reaches "
       "<b>3.299&times;</b> on the same hardware &mdash; and the ranking reverses between "
       "QFT and EfficientSU2.")],
     "fig4_ghz_chain_vs_star"),

    ("03", "Seed variability, stratified by stochastic source",
     "level 0 has a deterministic layout, so its spread is routing alone; levels 1 and 3 "
     "add stochastic SabreLayout &middot; worst configuration per family and map, chosen "
     "independently within each level",
     [("Routing variability",
       "Five seeds on QFT / heavy-hex / n = 20 / L0 span <b>5.419&times; to 7.527&times;</b>. "
       "Level 0 carries the larger relative dispersion despite its deterministic layout "
       "(p = 2.6&times;10<sup>&minus;6</sup>). A single-seed benchmark would have reported "
       "any point in that range.")],
     "fig6_seed_variability"),

    ("04", "The label-permutation control",
     "24 deterministically derived relabellings per constrained map &mdash; same graph "
     "every time, only the numbering changes &middot; SHA-256 derivation, reproducible on "
     "any platform &middot; 17,280 compilations",
     [("Labelling is a confound, and it is measurable",
       "Relabelling the same graph moves level-0 results by up to <b>15.70&times;</b>; this "
       "study's labelling is more favourable than every relabelling tested. At levels 1 and "
       "3 the spread falls to <b>1.06&ndash;1.23&times;</b> and the QFT / EfficientSU2 "
       "ranking holds in <b>24 of 24</b>."),
      ("And one claim did not survive",
       "GHZ star looked cheap on the line under this study's labelling &mdash; "
       "<b>1.87&times;</b> at level 3, against a relabelling median of <b>3.99&times;</b>. "
       "Under relabelling the star is cheaper on heavy-hex in <b>22 of 24</b>. That number "
       "is reported as labelling, not connectivity.")],
     "fig11_permutation_sweep"),
]

LIMITS = [
    "Compiler-level study, not physical hardware execution.",
    "One graph per topology class &mdash; heavy-hex results are Cairo's specific 27-node graph.",
    "Depends on the tested families, sizes, and the optimization set {0, 1, 3}.",
    "Compilation runtime is machine- and process-specific.",
    "Five seeds and 24 relabellings characterise, but do not exhaust, either space.",
]

stats_html = "".join(
    f'<div class="stat"><div class="v">{v}</div><div class="k">{k}</div></div>'
    for v, k in STATS)


def section(num, head, cap, findings, figname):
    finds = "".join(
        f'<div class="finding"><div class="fhead">{h}</div>'
        f'<div class="fbody">{b}</div></div>'
        for h, b in findings)
    return f"""
<div class="srow">
  <div class="sside">
    <div class="sechead"><span class="n">{num}</span><h2>{head}</h2></div>
    <div class="cap">{cap}</div>
    {finds}
  </div>
  <div class="sfig">{img(figname)}</div>
</div>"""


sections_html = "".join(section(*s) for s in SECTIONS)
limits_html = "".join(f"<li>{x}</li>" for x in LIMITS)

HTML = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {{ --k: 1; }}
@page {{ size: 841mm 1189mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 841mm; background: {PAPER}; }}
body {{ color: {INK}; font-family: 'Source Sans 3', sans-serif;
        padding: calc(24mm * var(--k)) calc(22mm * var(--k)); }}
.fig {{ display: block; }}
h1 {{ font-size: calc(29mm * var(--k)); line-height: 1.02; font-weight: 700;
      letter-spacing: calc(-0.55mm * var(--k)); }}
.sub {{ font-size: calc(12mm * var(--k)); font-weight: 300; color: {INK_SOFT};
        margin-top: calc(3mm * var(--k)); }}
.byline {{ font-size: calc(8mm * var(--k)); margin-top: calc(5mm * var(--k)); font-weight: 600; }}
.byline span {{ font-weight: 300; color: {INK_SOFT}; }}
.rule {{ height: calc(0.9mm * var(--k)); background: {INK};
         margin: calc(6mm * var(--k)) 0 calc(5mm * var(--k)); }}
.qbar {{ display: flex; gap: calc(9mm * var(--k)); align-items: flex-start; }}
.q {{ font-size: calc(9.2mm * var(--k)); font-weight: 600; line-height: 1.26; flex: 1.5; }}
.qnote {{ font-size: calc(6mm * var(--k)); color: {INK_SOFT}; line-height: 1.38; flex: 1;
          border-left: calc(0.8mm * var(--k)) solid {RULE};
          padding-left: calc(5.5mm * var(--k)); }}
.stats {{ display: flex; gap: calc(5mm * var(--k)); margin-top: calc(6mm * var(--k)); }}
.stat {{ flex: 1; border: calc(0.6mm * var(--k)) solid {RULE}; background: #fff;
         padding: calc(4.5mm * var(--k)) calc(5mm * var(--k));
         border-radius: calc(3mm * var(--k)); }}
.stat .v {{ font-size: calc(11.5mm * var(--k)); font-weight: 700;
            letter-spacing: calc(-0.25mm * var(--k)); }}
.stat .k {{ font-size: calc(5.4mm * var(--k)); color: {INK_SOFT};
            margin-top: calc(1.4mm * var(--k)); line-height: 1.3; }}

/* one section per row: sidebar carries the argument, figure carries the evidence */
.srow {{ display: flex; gap: calc(23mm * var(--k)); align-items: flex-start;
         margin-top: calc(17mm * var(--k)); padding-top: calc(6mm * var(--k));
         border-top: calc(0.6mm * var(--k)) solid {RULE}; }}
.sside {{ width: calc({SIDE_MM}mm * var(--k)); flex: none; }}
.sfig {{ flex: 1; min-width: 0; }}
.sechead {{ display: flex; align-items: baseline; gap: calc(4mm * var(--k)); }}
.sechead .n {{ font-family: 'JetBrains Mono', monospace; font-size: calc(7.2mm * var(--k));
               font-weight: 600; color: {FLAG}; }}
.sechead h2 {{ font-size: calc(10mm * var(--k)); font-weight: 700; line-height: 1.1;
               letter-spacing: calc(-0.2mm * var(--k)); }}
.cap {{ font-size: calc(6.1mm * var(--k)); color: {INK_SOFT}; font-weight: 300;
        line-height: 1.32; margin-top: calc(3.2mm * var(--k));
        padding-bottom: calc(4.5mm * var(--k));
        border-bottom: calc(0.6mm * var(--k)) solid {RULE}; }}
.finding {{ margin-top: calc(5mm * var(--k)); }}
.fhead {{ font-size: calc(8.2mm * var(--k)); font-weight: 700; line-height: 1.14;
          margin-bottom: calc(1.8mm * var(--k)); }}
.fbody {{ font-size: calc(7.1mm * var(--k)); line-height: 1.36; }}

.foot {{ display: flex; gap: calc(8mm * var(--k)); margin-top: calc(14mm * var(--k));
         padding-top: calc(5mm * var(--k)); border-top: calc(0.9mm * var(--k)) solid {INK}; }}
.foot h3 {{ font-size: calc(6.4mm * var(--k)); font-weight: 700;
            margin-bottom: calc(2.2mm * var(--k)); }}
.foot li {{ font-size: calc(5.2mm * var(--k)); line-height: 1.38; color: {INK_SOFT};
            margin-left: calc(5mm * var(--k)); }}
.foot p {{ font-size: calc(5.2mm * var(--k)); line-height: 1.42; color: {INK_SOFT}; }}
code {{ font-family: 'JetBrains Mono', monospace; font-size: 0.94em; }}
.qr {{ width: calc(31mm * var(--k)); }}
.scope {{ background: #fff; border: calc(0.6mm * var(--k)) solid {FLAG};
          border-radius: calc(3mm * var(--k)); padding: calc(4mm * var(--k));
          font-size: calc(5.4mm * var(--k)); line-height: 1.38; }}
.scope b {{ color: {FLAG}; }}
</style></head><body>

<h1>Quantifying Routing Overhead in Quantum Circuit Compilation</h1>
<div class="sub">A controlled comparison of hardware topologies &mdash; and of the labelling hiding inside one</div>
<div class="byline">Jos&eacute; Andr&eacute;s Auy&oacute;n C&oacute;bar<span>&nbsp;&nbsp;&middot;&nbsp;&nbsp;Universidad del Valle de Guatemala&nbsp;&nbsp;&middot;&nbsp;&nbsp;WEH Quantum Science and Technology Seminar</span></div>
<div class="rule"></div>

<div class="qbar">
  <div class="q">How much does restricted qubit connectivity inflate compiled quantum
  circuits, which interaction patterns are most sensitive to hardware topology &mdash; and
  how much of the measured effect is connectivity rather than how the physical qubits
  happen to be numbered?</div>
  <div class="qnote">A compiler study, not a physics demonstration. It measures compiler
  output under modeled connectivity constraints; it does not measure QPU fidelity and makes
  no quantum-advantage claim. <b>1,080 canonical compilations</b> plus <b>20,040</b> in a
  label-permutation control, all under Qiskit 2.5.1. Four circuit families &times; six
  logical sizes (4&ndash;24) &times; three topologies at 27 physical qubits &times; three
  optimization levels &times; five fixed seeds, with circuit, basis, level and seed held
  fixed while connectivity varies.</div>
</div>

<div class="stats">{stats_html}</div>
{sections_html}

<div class="foot">
  <div style="flex:1.05"><h3>Limitations</h3><ul>{limits_html}</ul></div>
  <div style="flex:1.05"><h3>Methodological integrity</h3>
    <div class="scope"><b>Level 0 measures labelling, not connectivity.</b> Relabelling the
    same graph moves it by up to 15.70&times; &mdash; about three times the largest topology
    effect measured anywhere here &mdash; so no level-0 number carries a topology claim.
    Where an exact embedding exists the result is label-invariant, <b>28 of 28</b>; every
    systematic shift falls where <code>VF2Layout</code> fails, <b>15 of 15</b>. No
    exceptions in either direction.</div></div>
  <div style="flex:0.95; display:flex; gap:calc(5mm * var(--k)); align-items:flex-start">
    <div><h3>Reproducible benchmark</h3>
      <p>Python 3.12 &middot; Qiskit 2.5.1 &middot; fixed seeds 11, 22, 33, 44, 55 &middot;
      locked dependencies. Recompiling all 1,080 canonical points reproduced the stored
      metrics <b>exactly, 1,080 of 1,080</b>. Sweep conditions derive from a SHA-256
      keystream, pinned by digest in the test suite.</p>
      <p style="margin-top:calc(2.2mm * var(--k))"><code>github.com/auyjos/quantum-routing-overhead</code></p>
    </div>
    <img class="qr" src="data:image/png;base64,{b64("fig9_repository_qr")}">
  </div>
</div>

</body></html>"""

pathlib.Path("poster_a0.html").write_text(HTML, encoding="utf-8")
print("wrote poster_a0.html", len(HTML) // 1024, "KB")
