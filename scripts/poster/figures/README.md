# Poster figures and page composition

Everything the A0 portrait poster is built from. Two rendering modes share one source:

- **default** — standalone figures, each with its own title and standfirst. Used for the
  Gamma deck and anywhere a figure appears on its own.
- **`QRO_POSTER=1`** — the same figures with titles and standfirsts suppressed and type
  sized for the composed page, which supplies those headings itself. Printing them twice
  wastes the vertical space the page needs for the charts.

## Layout note

Figures are deliberately wide (aspect 2.0–2.4). A0 portrait is 841 × 1189 mm; four
near-square figures stacked one per row overrun the page by roughly 2×, and shrinking
them to fit costs more type size than the extra rows buy back. The page pairs each wide
figure with a sidebar carrying that section's heading, caption and finding, so the space
either side of the figure holds the argument rather than sitting empty.

## Rebuild

```sh
# figure inputs
#   raw.csv                     canonical 1,080-row run
#   artifacts/runs/relabelling-sweep/   label-permutation control outputs

for s in fig_penalty fig_ghz fig_seed fig_permsweep; do
    QRO_POSTER=1 python "$s.py"        # -> figs/, move to figs_poster/
done
python fig_penalty.py two_qubit_count_penalty   # fig3, landscape only

python build_poster.py      # -> poster_a0.html, figures inlined as base64
python render_poster.py     # binary-searches --k for an exact one-page fit
python verify_poster.py     # re-derives every printed number from the CSVs
```

`render_poster.py` fits the layout by measurement rather than by hand, so swapping a
figure for one with a different aspect ratio re-fits the page instead of silently
overflowing it. `verify_poster.py` must pass before the PDF is shared: it reads the
numbers back out of the rendered HTML and recomputes each one from the journalled run
data, so a typo or a stale copy-paste fails loudly instead of being printed at A0.

## Shared design system

`style.py` holds the palette and axis treatment. Topology colours are fixed and never
remapped between figures:

| series | colour | role |
|---|---|---|
| Complete | `#7A828F` neutral grey, dashed | the 1× denominator |
| Heavy-hex (Cairo, 27q) | `#0E8C9E` teal | constrained |
| Linear (27q) | `#7A3FD4` violet | constrained |

Every figure carries one figure-level legend above its panels rather than labelling
series inside a single facet, and labels the shared y axis once for the whole grid.
