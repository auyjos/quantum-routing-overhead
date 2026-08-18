# Quantifying Routing Overhead in Quantum Circuit Compilation

## A controlled 27-qubit comparison of complete, line, and Cairo heavy-hex connectivity

**José Andrés Auyón Cóbar**

**Research question.** When every other major compiler input is fixed, how much do line and
heavy-hex connectivity change compiled two-qubit depth relative to complete connectivity?

## Controlled benchmark

- **1,080 successful canonical compilations:** 4 circuit families (QFT, GHZ chain, GHZ
  star, Efficient SU2) x 6 logical sizes (4, 8, 12, 16, 20, 24) x 3 topologies x 3
  optimization levels (0, 1, 3) x 5 fixed transpiler seeds (11, 22, 33, 44, 55).
- Every topology has 27 physical qubits and the common `rz,sx,x,cx` basis. The Cairo
  map is the **connected coupling graph** from FakeCairo, symmetrized for this controlled
  study; it is not the degraded calibrated backend target. [Figure 1; canonical topology
  metadata]
- QFT omits final swaps, keeping algorithmic output reversal separate from routing. [canonical
  circuit metadata]
- Timing pools the canonical run with two full, rotated-order, one-worker process repeats:
  3 process repeats x 5 fixed seeds are **crossed**, giving 15 observations per
  family-size-topology-level cell. Timing is local compiler timing, not QPU performance.
  [Figure 5; timing-validation review]

## Primary metric

**Two-qubit-depth penalty** = constrained compiled two-qubit depth / the matched
complete-connectivity compiled two-qubit depth. Matching fixes circuit family, logical size,
circuit hash, optimization level, seed, and basis. A ratio of 1 is the complete-connectivity
baseline; median and IQR summarize the five canonical seed outputs per plotted configuration.
[Figures 2 and 4; `summary_results.parquet`]

## Key results

- Across all 360 constrained canonical outputs per map, the line penalty is **2.691**
  (IQR **1.250-3.646**, range **1.000-4.870**) and Cairo is **2.909**
  (IQR **1.800-3.836**, range **1.000-7.527**). These pooled descriptive summaries
  span families, sizes, levels, and seeds; individual line-versus-Cairo ordering is
  circuit-dependent. [Figure 2; canonical `raw_results.csv`]
- Interaction pattern changes the result. Across 90 canonical GHZ outputs per family/map,
  GHZ chain on a line remains **1.000** (IQR **1.000-1.000**, range **1.000-1.000**),
  whereas GHZ star on a line is **3.299** (IQR **2.000-3.739**, range
  **1.333-4.870**). On Cairo, chain is **1.000** (IQR **1.000-2.893**, range
  **1.000-5.435**) and star is **3.261** (IQR **2.867-3.838**, range
  **1.000-5.364**). [Figure 4; canonical `raw_results.csv`]
- The Cairo chain median hides two distinct regimes and must be read stratified: only 61%
  of those 90 outputs are exactly 1.000. By level the medians are **4.026** at L0,
  **1.000** at L1, and **1.000** at L3; within L1 and L3 every size from 4 to 20 is
  **1.000** while n=24 is **2.304**. The L0 row is an identity-layout effect and the n=24
  column is a graph-forced one; they are not the same finding. [Figure 4; canonical
  `raw_results.csv`]
- Higher optimization levels coincide with lower canonical median penalties and higher
  repeat-pooled local compile times. For the line, L0 is **3.904** penalty
  (IQR **1.825-4.292**) at **2.229 ms** (IQR **2.015-2.525**) and L3 is
  **1.991** (IQR **1.250-2.315**) at **4.508 ms** (IQR **4.026-5.689**).
  For Cairo, L0 is **4.282** (IQR **3.492-5.160**) at **2.281 ms**
  (IQR **2.095-2.633**) and L3 is **2.174** (IQR **1.000-2.803**) at
  **4.860 ms** (IQR **4.162-5.618**). [Figure 5; canonical routing plus 3-run
  timing pool]
- Complete-connectivity L3 has a repeat-pooled median of **46.097 ms** (IQR
  **31.680-72.148**), versus **4.508 ms** for line and **4.860 ms** for Cairo
  L3. This broad repeated contrast is descriptive; fine line-versus-Cairo timing ranks
  are not claimed. [Figure 5; 3-run timing pool]

## Interpretation

The results compare **interaction-to-coupling compatibility under a chosen layout**. A
logical circuit defines required interactions, while the coupling map defines which
physical-qubit pairs can interact directly. Routing is required when the current placement
does not map an interaction to an allowed edge; another layout may remove an apparent
mismatch. Gate-count penalty measures the observed added work, while depth penalty measures
how much remains on the observed critical path after available parallelism.

Two claims here are forced by the coupling graphs and hold independently of any
transpiler. Cairo's longest simple path is exactly **21 nodes** (exhaustive search, with an
explicit witness), so no static placement can embed a 24-qubit GHZ chain there without
remapping. Cairo's simple-cycle lengths are exactly `{12, 20}`, so exact circular
embeddings are available at those sizes. Under Qiskit 2.5.1, the corresponding observed
results are a `2.304x` Cairo-chain penalty at L1 and L3 and a `1.000x` circular Efficient
SU(2) penalty at n=12 and n=20. Those magnitudes, routing heuristics, available parallelism,
topology rankings, and optimization-level effects could differ under another router or
release.

**Optimization level 0 is confounded with physical-qubit labeling, and a
label-permutation control shows the confound dominates that stratum.** At L0 Qiskit pins
the initial layout to `TrivialLayout`, the identity permutation. The circuit builders index
the GHZ chain and circular Efficient SU(2) on `(i, i+1)`, exactly how
`CouplingMap.from_line(27)` is labeled, while Cairo carries the FakeCairo labeling; at
n=24, 23 of 23 chain edges are natively satisfied on the line against 9 of 23 on Cairo.
A control re-ran each constrained map against relabelled copies of the same graph —
identical edges, degrees, diameter and mean path, only the physical-qubit numbering
permuted. Across 24 uniformly random relabellings per map, the identity labelling used in
this study is the single most favourable labelling tested at L0 on both maps: random
relabellings give pooled L0 medians of `11.3x` on the line (identity: `3.904x`) and
`6.1x` on Cairo (identity: `4.282x`), with GHZ chain on a relabelled line reaching
`15.7x` where identity reports `1.000x`. L0 is retained as a valid, declared Qiskit
preset condition and no stored value changes, but that stratum measures labelling, not
connectivity, and no L0 number in this study carries a topology claim. Excluding it, the
pooled constrained medians are `2.140x` on line and `2.304x` on Cairo, and the same
control shows levels 1 and 3 are close to label-invariant there: the across-relabelling
spread of pooled medians is `1.04x-1.20x`, with the identity labelling inside the
distribution. Optimization level 2 was deliberately outside the pre-registered core scope
from the start, so all comparisons are made within the tested set `{0, 1, 3}`.

**The mechanism is the layout pass.** Instrumenting `VF2Layout_stop_reason` over levels 1
and 3 (96 configurations, base and relabelled): wherever an exact subgraph embedding is
found — by VF2Layout, or by a trivial layout that already satisfies the coupling map —
the result is label-invariant, 28 of 28 with no exceptions. All 15 systematic labelling
shifts (base and relabelled seed ranges disjoint) fall where VF2 fails and the stochastic
SabreLayout chooses the layout, again with no exceptions. Labelling can only bite when
routing is genuinely required.

The GHZ comparison contrasts interaction shapes. GHZ chain uses
nearest-neighbor interactions and embeds on the line at every tested size and level,
producing a `1.000x` penalty. GHZ star requires one logical qubit to interact with every
other qubit, conflicting with maximum degree 2 on the line and 3 on Cairo. Its roughly
`3.3x` observed median penalty is consistent with that interaction-shape difference while
holding the logical task and qubit count fixed. **One star number is labelling-dependent
and must be quoted as such:** on the line at levels 1 and 3, the identity labelling
coincides with the best case of the relabelling distribution (identity `2.10x` pooled
against a random-relabelling median of `4.37x`, range `2.10x-5.09x`), and under typical
relabellings the star is cheaper on Cairo in 19 of 24 cases. The star's low line numbers
are a property of this study's labelling, not of line connectivity.

Circuit families reverse the topology ordering, the reversal survives without the L0
stratum, and the label-permutation control shows it is label-robust. QFT median
two-qubit-depth penalty is `2.691x` on line and `3.192x` on Cairo, whereas circular
Efficient SU(2) is `3.562x` on line and `2.599x` on Cairo; taken level by level, QFT
stays cheaper on line (`2.819x` L1, `2.155x` L3, against `3.108x` and `2.667x` on Cairo)
and Efficient SU(2) stays cheaper on Cairo (`2.250x` L1, `2.125x` L3, against `3.490x`
and `3.344x` on line). Under the control, QFT is cheaper on the line in 24 of 24 random
relabellings and Efficient SU(2) is cheaper on Cairo in 24 of 24. The defensible
conclusion is not that one sparse topology wins, but that hardware connectivity must be
evaluated against the workload's interaction graph.

Overhead generally grows as more of the device is occupied. Pooling families and levels, the
line median rises from `1.900x` at 4 logical qubits to `3.367x` at 24; Cairo rises from
`1.800x` to `3.661x`. Overall two-qubit-count penalties are `2.459x` for line and `2.522x`
for Cairo. The simultaneous increase in count and depth shows that routing adds operations,
while their differing ratios show that some of those operations can still be parallelized.

Optimization level changes the result without changing the coupling graph. Across both
constrained maps, QFT falls from `4.042x` at L0 to `2.223x` at L3, GHZ star from `4.158x`
to `2.087x`, and Efficient SU(2) from `4.292x` to `2.500x`, and the same levels coincide
with longer local compile times. This is consistent with the higher presets spending more
classical effort on layout, cancellation, and routing schedules; the level-to-quality and
level-to-time associations are observed under Qiskit 2.5.1 rather than established as a
mechanism here, and part of the L0 end of each range is the identity-layout effect noted
above. Complete connectivity remains an ideal denominator, not a claim about a real fully
connected 27-qubit processor. [Figures 2-5; canonical raw and summary results]

## Figure captions

1. **Topology comparison.** Saved, undirected 27-qubit coupling maps: complete has 351
   couplings and diameter 1; line has 26 and diameter 26; symmetrized Cairo heavy-hex has
   28 and diameter 12. No calibration or gate-direction data is used. [Figure 1; canonical
   topology metadata]
2. **Two-qubit-depth penalty.** Primary routing outcome versus logical size; each point is
   the five-seed canonical median and each band is its IQR. The dotted line is the
   complete-connectivity ratio of 1. [Figure 2; canonical `summary_results.parquet`]
3. **Two-qubit-count penalty.** The same controlled comparison for output two-qubit gate
   count, separating count expansion from depth expansion. [Figure 3; canonical
   `summary_results.parquet`]
4. **GHZ chain versus star.** Chain- and star-shaped interactions under line and Cairo
   connectivity, faceted by optimization level; five-seed medians and IQR bands expose
   the interaction-pattern contrast. [Figure 4; canonical `summary_results.parquet`]
5. **Optimization quality versus time.** Canonical median two-qubit-depth penalty against
   pooled local compiler time (log-scaled milliseconds). Vertical quality summaries pool
   120 canonical observations per topology+level (4 families x 6 sizes x 5 seeds);
   horizontal timing summaries pool 360 observations (the same grid x 3 process runs).
   IQR bars describe heterogeneous distributions, not independent uncertainty intervals.
   [Figure 5; canonical run plus r2/r3]
6. **Seed variability.** Five fixed-seed distributions at the highest-median-overhead
   configuration selected independently for each circuit-family/map pair; the dotted
   baseline is 1. The strata mix two stochastic sources and must be read separately:
   at L0 the layout is deterministic (`TrivialLayout`) and only `SabreSwap` routing is
   stochastic, while L1 and L3 add stochastic `SabreLayout`. L0 nonetheless shows the
   larger relative seed dispersion (median max/min `1.154` against `1.000` at L1 and
   `1.031` at L3; the gap survives normalising by median penalty). Within L1 and L3,
   a median penalty of exactly `1.000` implies zero seed spread with no exceptions
   (28 of 28 configurations), and the complete-connectivity denominator is fully
   seed-invariant at every level. [Figure 6; canonical `raw_results.csv`;
   seed-stratification review]
7. **Label-permutation control.** Pooled median penalty per labelling under 24 uniformly
   random physical-qubit relabellings of each constrained map, by optimization level,
   with the identity labelling marked; the reversal scatter and the VF2/Sabre mechanism
   attribution. [Figure 7; control runs]

## Limits and interpretation

This is a compiler-output benchmark under modeled, undirected connectivity--not a calibrated
hardware study, state-fidelity study, or QPU-performance measurement. Fixed seeds are
conditions, not independent replicates; descriptive medians/IQRs are reported without
significance tests. Three process repeats support pooled timing descriptions and broad
optimization-time contrasts, not deterministic per-point timing, causal topology-order
claims, or portable speed estimates. No quantum-advantage claim is made. [canonical
environment/configuration; timing-validation review]

## Conclusion

Under a common basis and matched compiler settings, constrained connectivity commonly raises
two-qubit depth, but the magnitude depends on the circuit interaction pattern and optimization
level. The line preserves a nearest-neighbor GHZ chain while star interactions show substantial
overhead; Cairo is not uniformly above or below line. Stronger optimization is associated here
with lower routing penalties and higher local compilation cost. [Figures 2, 4, and 5]

## Reproduction and provenance

**Accepted routing run:** `stage3-core-a2899b8e`

**Timing repeats:** `stage3-timing-r2-lhc-a2899b8e`, `stage3-timing-r3-hcl-a2899b8e`

**Label-permutation control runs.** The single-derangement control
(`configs/control-label-permutation.yaml`, 1,800 compilations), the 24-relabelling sweep
(18,720 compilations) and the VF2/Sabre mechanism attribution (960 instrumented
compilations) were collected under Qiskit 2.5.2 on Linux, not the canonical 2.5.1
environment. Identity-labelled results reproduced the canonical medians to within
0.0005x everywhere checked, but the control's numbers are quoted from its own runs and
should be re-collected alongside any fresh canonical set. Its stored permutations are
literals in `routing_overhead.topologies.PERMUTATIONS`; the 24 sweep permutations derive
from `random.Random(20260818)` in a single documented stream.

**Recorded commit:** `a2899b8ef46b41fc7829f3d9e8b106b069f76a39`

**Run-data reproducibility is code-only.** The repository includes the poster outputs, but
`.gitignore` excludes `artifacts/runs/*`, and these three run directories are not published
as a release, archive, or checksummed bundle. The run identifiers and commit above are the
provenance record of what produced the numbers on this poster, not a download: reproduction
means collecting a fresh set with the same configurations and locked dependencies. Routing
metrics are deterministic and should match exactly; compilation times are machine- and
process-specific and will not.

### Collect a fresh three-run timing set

```powershell
python -m routing_overhead.cli run --config configs/core.yaml --run-id fresh-core-canonical
python -m routing_overhead.cli run --config configs/core-timing-lhc.yaml --run-id fresh-timing-lhc
python -m routing_overhead.cli run --config configs/core-timing-hcl.yaml --run-id fresh-timing-hcl
python -m routing_overhead.cli aggregate --run artifacts/runs/fresh-core-canonical
python -m routing_overhead.cli plot --run artifacts/runs/fresh-core-canonical `
  --timing-run artifacts/runs/fresh-timing-lhc `
  --timing-run artifacts/runs/fresh-timing-hcl
```

**Machine-verification note (read-only; used for this draft).** An in-memory pandas check
loaded the canonical and two timing-repeat CSVs, verified canonical planned-point uniqueness
and three timing rows per planned point, and recomputed the cited descriptive summaries.

**Repository / QR code:** `https://github.com/auyjos/quantum-routing-overhead.git`
