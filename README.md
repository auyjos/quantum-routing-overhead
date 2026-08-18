# Quantum Routing Overhead

Controlled benchmark of how complete, line, and Cairo heavy-hex connectivity affect
Qiskit circuit compilation.

## Results and interpretation

The benchmark holds the logical circuit, 27-qubit width, `rz,sx,x,cx` basis,
optimization level, and transpiler seed fixed while changing only the coupling map.
Complete connectivity is the ideal reference. The primary metric is:

```text
two-qubit-depth penalty = constrained compiled 2Q depth / complete compiled 2Q depth
```

A value of `1x` means that connectivity added no two-qubit critical-path depth. The
accepted core grid contains 1,080 successful compilations: four circuit families, six
logical sizes, three topologies, three optimization levels, and five fixed seeds.

| Result (pooled over levels 0, 1, 3) | Line | Cairo heavy-hex |
|---|---:|---:|
| Overall median 2Q-depth penalty | 2.691x | 2.909x |
| Overall median 2Q-count penalty | 2.459x | 2.522x |
| QFT median 2Q-depth penalty | 2.691x | 3.192x |
| GHZ chain median 2Q-depth penalty | 1.000x | 1.000x |
| GHZ star median 2Q-depth penalty | 3.299x | 3.261x |
| Efficient SU(2) median 2Q-depth penalty | 3.562x | 2.599x |

**Read the level-0 stratum with care.** Qiskit's optimization level 0 pins the initial
layout to `TrivialLayout`, the identity permutation. The circuit builders index a GHZ
chain and a circular Efficient SU(2) on `(i, i+1)`, which is exactly how
`CouplingMap.from_line(27)` is labelled, so the line map is pre-aligned with the circuits
at level 0 while Cairo carries the FakeCairo labelling. Level 0 remains a valid, declared
Qiskit condition and no stored value is affected, but that third of the grid partly
measures physical-index alignment rather than connectivity alone, and it carries the
study's largest penalties. Excluding it, the pooled constrained medians fall to `2.140x`
on the line and `2.304x` on Cairo. Optimization level 2 was left outside the
pre-registered core scope from the start (see the implementation plan's optional list),
so every comparison here is made within the tested set `{0, 1, 3}`.

The central comparison is **interaction-to-coupling compatibility under a chosen
layout**: the circuit specifies which logical qubits must interact, while the coupling
map specifies which physical interactions are direct. Routing is required when the
current placement does not map an interaction to an allowed physical edge; a different
layout can remove an apparent mismatch. Two consequences follow from the coupling graphs
alone; the penalty magnitudes and other trends are observations under Qiskit 2.5.1's
heuristics.

- **Forced by the graph.** Cairo's longest simple path is exactly 21 nodes, so no static
  placement can embed a 24-qubit GHZ chain there without remapping. Cairo's simple-cycle
  lengths are exactly `{12, 20}`, so exact circular embeddings are available at those two
  sizes.
- **Observed here.** Under Qiskit 2.5.1, the non-embeddable 24-qubit Cairo chain has a
  `2.304x` median penalty at levels 1 and 3, while circular Efficient SU(2) reaches exactly
  `1.000x` at n=12 and n=20 under those levels. A GHZ chain stays at `1.000x` on the line
  at every size and level. A GHZ star conflicts with the low degree of both sparse maps
  and costs about `3.3x`. QFT's long-range interactions are costly on both sparse maps,
  more so on Cairo. Efficient SU(2)'s circular entanglement fares better on Cairo, while
  a line breaks the ring.

The pooled Cairo GHZ-chain median of `1.000x` is not a flat surface. Only 61% of those 90
outputs are exactly 1, and the two modes have different causes:

| Cairo GHZ chain, median 2Q-depth penalty | n=4 | n=8 | n=12 | n=16 | n=20 | n=24 |
|---|---:|---:|---:|---:|---:|---:|
| Level 0 | 1.000x | 3.000x | 4.364x | 3.933x | 4.263x | 4.696x |
| Level 1 | 1.000x | 1.000x | 1.000x | 1.000x | 1.000x | **2.304x** |
| Level 3 | 1.000x | 1.000x | 1.000x | 1.000x | 1.000x | **2.304x** |

The level-0 row (pooled `4.026x`) is the identity-layout effect above: a zero-routing
embedding exists for n <= 21 and `TrivialLayout` does not find it. The n=24 column is the
structural result — 24 exceeds Cairo's 21-node longest path, so no such embedding exists
at any level.

Connectivity is therefore not a scalar ranking: Cairo is not uniformly better or worse
than a line. The support for that is the per-family reversal, which holds at levels 1 and
3 individually and so does not depend on the level-0 stratum: QFT is cheaper on the line
(`2.819x` at L1, `2.155x` at L3) than on Cairo (`3.108x`, `2.667x`), while circular
Efficient SU(2) is cheaper on Cairo (`2.250x`, `2.125x`) than on the line (`3.490x`,
`3.344x`). Median penalty also generally increases with circuit size; from 4 to 24 logical
qubits it rises from `1.900x` to `3.367x` on the line and from `1.800x` to `3.661x` on
Cairo.

Higher optimization levels coincided with lower routing penalties and more local compiler
time. For example, the pooled constrained QFT median falls from `4.042x` at level 0 to
`2.223x` at level 3. These timings describe the local compiler, not QPU execution.

This is a modeled, undirected-connectivity benchmark. It does not include calibration,
directional gate quality, noise, fidelity, or hardware execution time, and it makes no
quantum-advantage claim. See [the poster interpretation](poster/poster-content.md) for the
full claim boundaries and figure-by-figure explanation.

## Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.lock.txt
python -m pip install -e . --no-deps
```

## Development

```powershell
pytest
ruff check .
```

## Smoke benchmark

```powershell
python -m routing_overhead.cli validate-config configs/smoke.yaml
python -m routing_overhead.cli run --config configs/smoke.yaml
```

Run the core grid only after the smoke benchmark passes:

```powershell
python -m routing_overhead.cli run --config configs/core.yaml
```

## Label-permutation control

Qiskit's `TrivialLayout` maps logical qubit i to physical qubit i, and the GHZ chain and
circular Efficient SU(2) builders index their entanglers on `(i, i+1)` — exactly how
`CouplingMap.from_line(27)` numbers its nodes. A penalty that depends on that coincidence
is measuring labelling, not connectivity.

`configs/control-label-permutation.yaml` pairs each constrained map with a relabelled
copy of the **same graph**: identical edge count, degree sequence, diameter and mean
shortest path, with the physical-qubit numbering permuted so no `(i, i+1)` pair survives
as an edge. `control` then compares the two and writes `label_invariance.csv` and
`label_invariance_by_level.csv`.

```powershell
python -m routing_overhead.cli run --config configs/control-label-permutation.yaml `
  --run-id control-label-permutation
python -m routing_overhead.cli aggregate --run artifacts/runs/control-label-permutation
python -m routing_overhead.cli control --run artifacts/runs/control-label-permutation
```

A shift is only reported as **systematic** when the base and control seed ranges are
disjoint, so it cannot be produced by stochastic routing scatter. Each level of each base
topology is then classified `label-invariant`, `noise-only`, or `label-sensitive`.

## Poster figures

`plot` draws the poster figure set as PNG (300 dpi) and SVG into `<run>/figures/`.
Compilation-time figures need the process repeats; pass each repeat run directory
with `--timing-run`. A repeat that does not reproduce the canonical run's non-time
outputs exactly is rejected instead of pooled.

```powershell
python -m routing_overhead.cli aggregate --run artifacts/runs/fresh-core-canonical
python -m routing_overhead.cli plot --run artifacts/runs/fresh-core-canonical `
  --timing-run artifacts/runs/fresh-timing-lhc `
  --timing-run artifacts/runs/fresh-timing-hcl
```

The publication-ready deliverables are included in the repository:

- [A0 landscape poster (PDF)](output/pdf/quantum-routing-overhead-poster-a0-landscape.pdf)
- [A0 landscape poster preview (PNG)](output/pdf/quantum-routing-overhead-poster-a0-landscape.png)
- [Individual infographic assets (PNG and SVG)](output/infographic-assets/)

## Reproduction and provenance

The reproducibility package is **code-only with respect to run data**: the repository also
includes the poster outputs above, but `.gitignore` excludes `artifacts/runs/*`. The
accepted run directories are not published as a release, archive, or checksummed bundle,
so a fresh clone reproduces the study by collecting its own runs rather than by re-reading
the ones behind the numbers above. The accepted results were produced at commit
`a2899b8ef46b41fc7829f3d9e8b106b069f76a39` from run `stage3-core-a2899b8e` with timing
repeats `stage3-timing-r2-lhc-a2899b8e` and `stage3-timing-r3-hcl-a2899b8e`; those
identifiers are the provenance record, not a download.

Collect a fresh canonical run plus the two rotated-order timing repeats, then aggregate and
plot them:

```powershell
python -m routing_overhead.cli run --config configs/core.yaml --run-id fresh-core-canonical
python -m routing_overhead.cli run --config configs/core-timing-lhc.yaml --run-id fresh-timing-lhc
python -m routing_overhead.cli run --config configs/core-timing-hcl.yaml --run-id fresh-timing-hcl
python -m routing_overhead.cli aggregate --run artifacts/runs/fresh-core-canonical
python -m routing_overhead.cli plot --run artifacts/runs/fresh-core-canonical `
  --timing-run artifacts/runs/fresh-timing-lhc `
  --timing-run artifacts/runs/fresh-timing-hcl
```

Routing metrics are deterministic under the locked dependency set and should match
exactly. Compilation times will not: they are machine- and process-specific, which is why
three processes are collected and pooled.
