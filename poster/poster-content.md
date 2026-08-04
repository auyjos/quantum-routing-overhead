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
   baseline is 1. [Figure 6; canonical `raw_results.csv`]

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

**Recorded commit:** `a2899b8ef46b41fc7829f3d9e8b106b069f76a39`

### Re-render the distributed accepted artifact bundle

```powershell
python -m routing_overhead.cli plot --run artifacts/runs/stage3-core-a2899b8e `
  --timing-run artifacts/runs/stage3-timing-r2-lhc-a2899b8e `
  --timing-run artifacts/runs/stage3-timing-r3-hcl-a2899b8e
```

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
