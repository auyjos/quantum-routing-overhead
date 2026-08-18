# Quantifying Routing Overhead in Quantum Circuit Compilation

## A Controlled Comparison of Hardware Topologies

**José Andrés Auyón Cóbar** · Universidad del Valle de Guatemala
WEH Quantum Science and Technology Seminar

A controlled 27-qubit benchmark of complete, heavy-hex and linear connectivity under the Qiskit transpiler. **1,080 canonical compilations**, plus **20,040** more in a label-permutation control that tests whether the measured effects are connectivity or physical-qubit numbering. Every number on this page is recomputed from the study's saved results file.

---

## The Research Question

**How much does restricted qubit connectivity inflate compiled quantum circuits, and which circuit interaction patterns are most sensitive to hardware topology?**

When every other major compiler input is held fixed — circuit instance, physical-qubit count, gate basis, optimization level, transpiler seed — how much do line and heavy-hex connectivity change compiled two-qubit depth relative to complete connectivity?

Four secondary questions follow: how complete, heavy-hex and linear connectivity compare; which circuit families pay the most; how far Qiskit's optimization levels claw the overhead back; and how much variability stochastic SABRE routing introduces across transpiler seeds.

This is a **compiler study**, not a physics demonstration. It measures compiler output under modeled connectivity constraints. It does not measure QPU fidelity and makes no quantum-advantage claim.

---

## 1 · The Problem

![Routing forces extra qubit movement](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig0_routing_problem.png)

A logical circuit declares which qubits must interact. A coupling map declares which physical qubit pairs *can* interact directly. When the current placement does not map a required interaction onto an allowed edge, the compiler must insert SWAP operations to move qubits together — and often to move them back.

**Restricted connectivity can force additional qubit movement before a logical interaction can execute.** Each inserted SWAP adds two-qubit operations, and any SWAP that cannot be parallelized adds two-qubit *depth*: more sequential layers on the critical path.

Gate-count penalty measures the added work. Depth penalty measures how much of that work survives after available parallelism. This study reports both, and treats two-qubit depth as the primary outcome.

---

## 2 · Controlled Experiment

![Controlled experiment design](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig7_experiment_design.png)

**Independent variable:** hardware connectivity topology.
**Controlled:** circuit instance and circuit hash, physical-qubit count (27 everywhere), basis gates (`rz, sx, x, cx`), optimization level, and transpiler seed.

4 circuit families × 6 logical sizes × 3 topologies × 3 optimization levels × 5 fixed seeds = **1,080 successful compilations** under Qiskit 2.5.1.

QFT omits the final swaps, keeping algorithmic output reversal separate from routing overhead. Timing is pooled over the canonical run plus two full rotated-order, one-worker process repeats — 3 process repeats × 5 fixed seeds, crossed, giving 15 observations per family–size–topology–level cell.

---

## Three Coupling Maps, 27 Physical Qubits Each

![Topology comparison](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig1_topologies.png)

| | Couplings | Degree | Diameter | Mean path |
|---|---|---|---|---|
| **Complete** — idealized baseline | 351 | 26–26 | 1 | 1.00 |
| **Heavy-hex** — hardware-representative | 28 | 1–3 | 12 | 4.95 |
| **Linear** — restrictive topology | 26 | 1–2 | 26 | 9.33 |

The heavy-hex map is the **connected coupling graph** taken from FakeCairo and symmetrized for this controlled study. It is not the degraded calibrated backend target, and no calibration or gate-direction data is used anywhere.

---

## 3 · Primary Result — Two-Qubit Depth Penalty

![Two-qubit depth penalty vs logical qubit count](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig2_two_qubit_depth_penalty.png)

**Two-qubit depth penalty = constrained-topology two-qubit depth ÷ matched complete-connectivity two-qubit depth.** Matching fixes circuit family, logical size, circuit hash, optimization level, seed and basis. Complete connectivity is the 1× denominator by construction.

Across all 360 constrained compilations per map, the **line** penalty is **2.691×** (IQR 1.250–3.646, range 1.000–4.870) and **heavy-hex** is **2.909×** (IQR 1.800–3.836, range 1.000–7.527). These pooled summaries span families, sizes, levels and seeds; individual line-versus-heavy-hex ordering is circuit-dependent.

Overhead generally grows as more of the device is occupied. Pooling families and levels, the line median rises from **1.900× at 4 logical qubits to 3.367× at 24**; heavy-hex rises from **1.800× to 3.661×**.

---

## Gate Count Expands Too — But Not In Step

![Two-qubit gate-count penalty](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig3_two_qubit_count_penalty.png)

Pooled two-qubit **count** penalties are **2.459×** for the line and **2.522×** for heavy-hex, against depth penalties of 2.691× and 2.909×.

Count and depth rise together, which shows routing genuinely adds operations. Their differing ratios show that some of those added operations still get parallelized away from the critical path.

---

## 4A · Interaction Structure Matters

![GHZ chain versus GHZ star](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig4_ghz_chain_vs_star.png)

Same logical task, same qubit count, same compiler settings — only the shape of the required interactions differs. Across 90 canonical outputs per family/map:

| | Linear | Heavy-hex |
|---|---|---|
| **GHZ Chain** | **1.000×** (IQR 1.000–1.000, range 1.000–1.000) | **1.000×** (IQR 1.000–2.893, range 1.000–5.435) |
| **GHZ Star** | **3.299×** (IQR 2.000–3.739, range 1.333–4.870) | **3.261×** (IQR 2.867–3.838, range 1.000–5.364) |

GHZ chain uses nearest-neighbour interactions and embeds on the line at **every** tested size and level. GHZ star requires one logical qubit to interact with every other, conflicting with maximum degree 2 on the line and 3 on heavy-hex; its roughly 3.3× median penalty is consistent with that interaction-shape difference alone.

**The heavy-hex chain median hides two regimes and must be read stratified.** Only 61% of those 90 outputs are exactly 1.000. By level the medians are **4.026× at L0, 1.000× at L1, 1.000× at L3**; within L1 and L3 every size from 4 to 20 is 1.000× while **n=24 is 2.304×**. The L0 row is an identity-layout effect; the n=24 column is graph-forced. They are not the same finding.

---

## Two Claims Forced by the Graphs Themselves

These hold independently of any transpiler, and were re-verified by exhaustive search on the saved coupling graph.

**Heavy-hex's longest simple path is exactly 21 nodes.** No static placement can embed a 24-qubit GHZ chain there without remapping — which is precisely the 2.304× penalty observed at n=24, L1 and L3.

**Heavy-hex's simple-cycle lengths are exactly {12, 20}.** Exact circular embeddings are available at those sizes and nowhere else — which is precisely why circular EfficientSU2 lands at **1.000× at n=12 and n=20**, and at 2.13×–2.91× at every other size.

**At n=24 under the identity layout,** 23 of 23 GHZ-chain edges are natively satisfied on the line against **9 of 23** on heavy-hex.

---

## Neither Sparse Topology Wins Outright

![Topology ordering reverses by circuit family](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig8_topology_reversal.png)

Circuit families reverse the topology ordering, and the reversal survives without the L0 stratum.

QFT median two-qubit depth penalty is **2.691× on line** against **3.192× on heavy-hex**, whereas circular EfficientSU2 is **3.563× on line** against **2.599× on heavy-hex**. Level by level, QFT stays cheaper on line (2.819× L1, 2.155× L3, against 3.108× and 2.667×) and EfficientSU2 stays cheaper on heavy-hex (2.250× L1, 2.125× L3, against 3.490× and 3.344×).

**The defensible conclusion is not that one sparse topology wins, but that hardware connectivity must be evaluated against the workload's interaction graph.**

---

## 4B · Compiler Optimization Trade-Off

![Optimization quality versus compilation time](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig5_optimization_tradeoff.png)

**Does spending more compiler time produce a better routed circuit?** Here, yes — and the extra time is real.

| | L0 penalty | L3 penalty | L0 time | L3 time |
|---|---|---|---|---|
| **Linear** | 3.904× (IQR 1.825–4.292) | 1.991× (IQR 1.250–2.315) | 2.36 ms | 12.02 ms |
| **Heavy-hex** | 4.282× (IQR 3.492–5.160) | 2.174× (IQR 1.000–2.803) | 3.11 ms | 12.72 ms |
| **Complete** | 1.000× | 1.000× | 4.02 ms | 63.84 ms |

Across both constrained maps, QFT falls from 4.042× at L0 to 2.223× at L3, GHZ star from 4.158× to 2.087×, and EfficientSU2 from 4.292× to 2.500×. GHZ chain is 1.000× at every level.

Level-to-quality and level-to-time associations are *observed* under Qiskit 2.5.1, not established as a mechanism. Optimization level 2 was deliberately outside the pre-registered core scope, so all comparisons are made within the tested set {0, 1, 3}.

---

## Optimization Level 0 Measures Labelling, Not Connectivity

At L0 Qiskit pins the initial layout to `TrivialLayout`, the identity permutation. The circuit builders index the GHZ chain and circular EfficientSU2 on `(i, i+1)` — exactly how `CouplingMap.from_line(27)` is labeled — while heavy-hex carries the FakeCairo labeling.

This was first stated as a suspicion. It is now **measured**: relabelling the same graph moves L0 results by up to **15.70×**, roughly three times the largest topology effect measured anywhere in this study.

L0 is retained as a valid, declared Qiskit preset condition and **no stored value is changed**. But no L0 number carries a topology claim. Excluding that stratum, the pooled constrained medians fall to **2.140× on line and 2.304× on heavy-hex**.

---

## 4C · SABRE Seed Variability

![Seed variability](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig6_seed_variability.png)

**Repeated transpilation is necessary because stochastic routing can produce different compiled circuits for the same logical input.**

At the highest-median-overhead configuration of each family/map pair, the five fixed seeds (11, 22, 33, 44, 55) span:

- **QFT on heavy-hex, n=20, L0** — min 5.419×, median 6.216×, max 7.527×: a **2.11× spread** from seed choice alone
- **GHZ star on heavy-hex, n=24, L0** — 4.391× to 5.348×
- **GHZ chain on heavy-hex, n=24, L0** — 4.478× to 5.435×
- **GHZ chain on the line, n=4** — 1.000× to 1.000×: no spread at all

Variability is not uniform. Of the 144 constrained family–size–topology–level configurations, **43% show zero seed spread** and the rest are dominated by heavy-hex at L0. In every family/map pair the worst-median configuration falls at optimization level 0.

Fixed seeds are *conditions*, not independent replicates. Medians and IQRs are reported descriptively, without significance tests.

---

## 5 · Supporting Metrics

**Two-Qubit Depth Penalty — primary outcome**
Additional sequential two-qubit layers introduced by topology.
Line **2.691×** · Heavy-hex **2.909×**

**Total Depth Penalty**
Compiled total depth relative to complete connectivity.
Line **2.415×** · Heavy-hex **2.500×**

**Two-Qubit Gate-Count Penalty**
Additional two-qubit operations relative to the baseline.
Line **2.459×** · Heavy-hex **2.522×**

**Compilation Time**
Local wall-clock transpilation time, pooled over 3 process repeats.
Line **4.86 ms** · Heavy-hex **5.46 ms** · Complete **6.26 ms** median; at L3 the complete-connectivity median rises to **63.84 ms**.
---

## 6 · The Label-Permutation Control

![Label-permutation control](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig11_permutation_sweep.png)

**If a result is about connectivity, renumbering the physical qubits must not change it.** So the whole experiment was re-run on 24 relabelled copies of each constrained map — same edges, same degrees, same diameter, same mean path length, only the numbering differs. **17,280 additional compilations across 48 relabelled coupling maps**, identical settings throughout.

Permutations derive from a SHA-256 keystream with rejection sampling, not `random.Random`, and the resulting set is pinned by digest in the test suite — so the control reproduces bit-for-bit on any platform and any Python build.

**What survives.** At levels 1 and 3 the across-labelling spread collapses to **1.06–1.23×**, and the topology ranking that matters holds unanimously: QFT is cheaper on the line in **24 of 24** relabellings, circular EfficientSU2 cheaper on heavy-hex in **24 of 24**.

**What does not.** At level 0 this study's labelling is more favourable than *every* relabelling tested, on both maps — relabelling medians of 10.57× on line and 6.12× on heavy-hex against the identity's much lower values.

---

## The Mechanism, and One Retracted Claim

**Why label sensitivity appears exactly where it does.** Instrumenting `VF2Layout_stop_reason` over 960 compilations resolves it with no exceptions in either direction: where VF2Layout finds an exact embedding the result is label-invariant, **28 of 28**; every systematic shift falls where VF2 fails and stochastic SabreLayout chooses the layout instead, **15 of 15**.

**And one claim did not survive the control.** Under this study's labelling, GHZ star looked cheap on the line at level 3 — **1.87×**. Under relabelling the median is **3.99×** (range 2.00–4.84×), and the star is cheaper on *heavy-hex* in **22 of 24** relabellings. That number is now reported as an artifact of labelling, not as a property of connectivity.

Reporting a result the control overturned is the point of running one.


## What We Found

**01 — Connectivity**
Constrained connectivity commonly raises two-qubit depth: median **2.691× on the line** and **2.909× on heavy-hex** across 360 compilations each. Dropping the confounded level 0 stratum, these fall to **2.140×** and **2.304×**.

**02 — Circuit structure**
Interaction shape dominates. GHZ chain on the line stays at exactly **1.000×** at every size and level, while GHZ star reaches **3.299×** on the same hardware — and the topology ranking reverses between QFT and EfficientSU2.

**03 — Optimization**
Level 3 roughly halves the penalty against level 0 — **3.904× → 1.991×** on the line and **4.282× → 2.174×** on heavy-hex — at 5× the local compile time (2.36 → 12.02 ms; 3.11 → 12.72 ms).

**04 — Routing variability**
Stochastic routing matters at the hard end. Five seeds on QFT / heavy-hex / n=20 / L0 span **5.419× to 7.527×**, while 43% of all constrained configurations show no seed spread at all.

**05 — Labelling is a confound, and it is measurable**
Relabelling the same graph moves level-0 results by up to **15.70×**; this study's labelling is more favourable than every relabelling tested. At levels 1 and 3 the spread falls to **1.06–1.23×** and the QFT / EfficientSU2 ranking holds in **24 of 24**.

**06 — And one claim did not survive**
GHZ star looked cheap on the line under this study's labelling — **1.87×** at level 3, against a relabelling median of **3.99×**. Under relabelling the star is cheaper on heavy-hex in **22 of 24**. That number is reported as labelling, not connectivity.

---

## Methodological Integrity

**Controlled topology benchmark.** The primary experiment isolates connectivity by keeping physical-qubit count, gate basis, logical circuit, optimization level and transpiler seed consistent across topology comparisons.

**This study evaluates compiler output under modeled connectivity constraints. It does not measure physical QPU fidelity and does not demonstrate quantum advantage.**

**Level 0 measures labelling, not connectivity.** Relabelling the same graph moves it by up to 15.70× — about three times the largest topology effect measured anywhere here. Where an exact embedding exists the result is label-invariant, 28 of 28; every systematic shift falls where `VF2Layout` fails, 15 of 15.

The interpretation throughout is *interaction-to-coupling compatibility under a chosen layout*. Routing is required when the current placement does not map an interaction onto an allowed edge; a different layout may remove an apparent mismatch. Complete connectivity remains an ideal denominator, not a claim about any real fully connected 27-qubit processor.

---

## Limitations

- Compiler-level study, not physical hardware execution
- Heavy-hex connectivity derived from a hardware-representative coupling graph, symmetrized and undirected
- Results depend on the tested circuit families, sizes, and the optimization set {0, 1, 3}
- Compilation runtime reflects the test environment; it is machine- and process-specific and will not reproduce elsewhere
- One graph per topology class — heavy-hex results are Cairo's specific 27-node graph
- Five transpiler seeds and 24 relabellings characterize, but do not exhaust, either space
- Magnitudes, routing heuristics, topology rankings and optimization-level effects could differ under another router or Qiskit release

---

## Reproducible Benchmark

![Repository QR code](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig9_repository_qr.png)

**github.com/auyjos/quantum-routing-overhead**

Python 3.12.13 · Qiskit 2.5.1 · fixed transpiler seeds 11, 22, 33, 44, 55 · saved raw and summary results · locked dependencies · reproducible experiment configuration.

Recompiling all 1,080 canonical points reproduced the stored metrics **exactly, 1,080 of 1,080**. Label-permutation conditions derive from a SHA-256 keystream, pinned by digest in the test suite.

```
python -m routing_overhead.cli run --config configs/core.yaml --run-id fresh-core-canonical
python -m routing_overhead.cli run --config configs/core-timing-lhc.yaml --run-id fresh-timing-lhc
python -m routing_overhead.cli run --config configs/core-timing-hcl.yaml --run-id fresh-timing-hcl
python -m routing_overhead.cli aggregate --run artifacts/runs/fresh-core-canonical
python -m routing_overhead.cli plot --run artifacts/runs/fresh-core-canonical \
  --timing-run artifacts/runs/fresh-timing-lhc --timing-run artifacts/runs/fresh-timing-hcl
```

**Run-data reproducibility is code-only.** `.gitignore` excludes `artifacts/runs/*`, so reproduction means collecting a fresh set with the same configurations and locked dependencies. Routing metrics are deterministic and should match exactly; compilation times are machine-specific and will not.

Figures and statistics on this page were regenerated from `output/data/quantum-routing-overhead-results.json` (run `fresh-core-canonical`, commit `fe343d5`) together with the two timing repeats `fresh-timing-lhc` and `fresh-timing-hcl`.
