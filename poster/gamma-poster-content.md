# Quantifying Routing Overhead in Quantum Circuit Compilation

## A controlled comparison of hardware topology — and the hidden effect of physical-qubit labelling

**José Andrés Auyón Cóbar** · Universidad del Valle de Guatemala
WEH Quantum Science and Technology Seminar

A controlled 27-qubit benchmark of complete, heavy-hex and linear connectivity under the Qiskit transpiler. **1,080 canonical compilations**, plus **20,040** more in a label-permutation control that tests whether the measured effects are connectivity at all. Every number here is recomputed from the study's saved results file.

---

## Unexpected result

**Physical-qubit labelling can dominate the apparent topology effect.**

Relabelling the *same* coupling graph — same edges, same degrees, same diameter, same mean path length, only the integer names change — moves optimization-level-0 results by up to **15.70×**. That is about three times the largest topology effect measured anywhere in this study.

And one of this study's own conclusions did not survive the control.

The rest of this deck is the evidence for that, and for what remains true once it is accounted for.

---

## The Four Numbers

**2.140× / 2.304×** — robust topology penalty, line / heavy-hex, levels 1 and 3.
The headline result, with the confounded stratum removed.

**15.70×** — largest level-0 shift from relabelling the same graph.
The confound, measured rather than asserted.

**24 of 24** — relabellings that preserve the QFT / EfficientSU2 ordering.
What survives the control, unanimously.

**1,080 / 1,080** — canonical results reproduced exactly on a clean rebuild.
Locked dependencies, fixed seeds, journalled runs.

---

## The Research Question

**How much does restricted qubit connectivity inflate compiled quantum circuits, which interaction patterns are most sensitive to hardware topology — and how much of the measured effect is connectivity rather than how the physical qubits happen to be numbered?**

When every other major compiler input is held fixed — circuit instance, physical-qubit count, gate basis, optimization level, transpiler seed — how much do line and heavy-hex connectivity change compiled two-qubit depth relative to complete connectivity?

This is a **compiler study**, not a physics demonstration. It measures compiler output under modeled connectivity constraints. It does not measure QPU fidelity and makes no quantum-advantage claim.

---

## The Problem

![Routing forces extra qubit movement](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig0_routing_problem.png)

A logical circuit declares which qubits must interact. A coupling map declares which physical qubit pairs *can* interact directly. When the current placement does not map a required interaction onto an allowed edge, the compiler must insert SWAP operations to move qubits together — and often to move them back.

Each inserted SWAP adds two-qubit operations, and any SWAP that cannot be parallelized adds two-qubit *depth*: more sequential layers on the critical path.

Gate-count penalty measures the added work. Depth penalty measures how much of that work survives after available parallelism. This study reports both, and treats two-qubit depth as the primary outcome.

---

## What Is Measured

**Two-qubit depth penalty = constrained-topology two-qubit depth ÷ matched complete-connectivity two-qubit depth.**

Every number is a ratio of one compilation to another, never a raw depth. Matching fixes circuit family, logical size, circuit hash, optimization level, seed and basis — so the only difference between numerator and denominator is which physical qubit pairs may interact.

**1.000× means restricted connectivity cost nothing at all.**

Complete connectivity is the 1× denominator by construction. It is an ideal reference, not a claim about any real fully connected 27-qubit processor.

---

## The Controlled Design

![Controlled experiment design](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig7_experiment_design.png)

**Independent variable:** hardware connectivity topology.
**Held fixed:** circuit instance and circuit hash, physical-qubit count (27 everywhere), basis gates (`rz, sx, x, cx`), optimization level, and transpiler seed.

4 circuit families × 6 logical sizes × 3 topologies × 3 optimization levels × 5 fixed seeds = **1,080 compilations** under Qiskit 2.5.1.

Plus **20,040 in the control**: 17,280 relabelling sweep + 1,800 matched baselines + 960 `VF2Layout` instrumentation.

QFT omits the final swaps, keeping algorithmic output reversal separate from routing overhead.

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

## 1 · Routing Overhead Is Real

![Two-qubit depth penalty vs logical qubit count](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/canva/figures/fig2_two_qubit_depth_penalty.png)

Excluding level 0, the median penalty is **2.140× on the line** and **2.304× on heavy-hex**.

Including level 0 it is **2.691×** and **2.909×** across 360 constrained compilations per map — but section 4 shows why no level-0 number can carry a topology claim.

Overhead generally grows as more of the device is occupied, and individual line-versus-heavy-hex ordering is circuit-dependent rather than fixed.

---

## Optimization Pays For Itself

![Optimization quality vs time](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig5_optimization_tradeoff.png)

Level 3 roughly halves the penalty against level 0 — **3.904× → 1.991×** on the line, **4.282× → 2.174×** on heavy-hex — at about **5× the local compile time**.

Compilation runtime reflects the test environment; it is machine- and process-specific and will not reproduce elsewhere.

---

## 2 · Interaction Structure Decides Which Topology Pays

![Interaction structure](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/canva/figures/fig12_interaction_structure.png)

Median over levels 1 and 3, all sizes and seeds. Level 0 is excluded throughout.

**GHZ chain sits at exactly 1.000× on both constrained maps** — the line already *is* its interaction graph, so restricting connectivity costs literally nothing.

**QFT is cheaper on the line** (**2.321×** against **2.897×**) while **circular EfficientSU2 is cheaper on heavy-hex** (**2.125×** against **3.427×**).

The ordering reverses between two dense circuits on identical hardware. "Sparser connectivity is worse" is false as a general statement — it depends on which circuit.

---

## 3 · The Compiler Itself Is Stochastic

![Seed variability](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/canva/figures/fig13_seed_focus.png)

**Repeated transpilation is necessary because stochastic routing can produce different compiled circuits for the same logical input.**

The widest configuration — QFT on heavy-hex, n = 20, level 0 — spans **5.419× to 7.527×** on seed choice alone. A single-seed benchmark would have reported any point in that range as *the* result.

Level 0 carries the larger *relative* dispersion despite its deterministic layout (Mann-Whitney p = 2.6e-06), but spread does not vanish at level 3.

Fixed seeds are *conditions*, not independent replicates. Medians and IQRs are reported descriptively.

---

## 4 · The Label-Permutation Control

![Label-permutation control](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/canva/figures/fig11_permutation_sweep.png)

**If a result is about connectivity, renumbering the physical qubits must not change it.**

So the whole experiment was re-run on 24 relabelled copies of each constrained map — same edges, same degrees, same diameter, same mean path length, only the numbering differs. **17,280 additional compilations across 48 relabelled coupling maps**, identical settings throughout.

Permutations derive from a SHA-256 keystream with rejection sampling, not `random.Random`, and the resulting set is pinned by digest in the test suite — so the control reproduces bit-for-bit on any platform.

---

## What Survives, and What Does Not

**What survives.** At levels 1 and 3 the across-labelling spread collapses to **1.06–1.23×**, and the topology ordering that matters holds unanimously: QFT cheaper on the line in **24 of 24** relabellings, circular EfficientSU2 cheaper on heavy-hex in **24 of 24**.

**What does not.** At level 0 this study's labelling is more favourable than *every* relabelling tested, on both maps — relabelling medians of 10.57× on line and 6.12× on heavy-hex.

**The mechanism is exact.** Instrumenting `VF2Layout_stop_reason` over 960 compilations resolves it with no exceptions in either direction: where VF2Layout finds an exact embedding the result is label-invariant, **28 of 28**; every systematic shift falls where VF2 fails and stochastic SabreLayout chooses the layout instead, **15 of 15**.

---

## And One Claim Did Not Survive

Under this study's labelling, GHZ star looked cheap on the line at level 3 — **1.87×**.

Under relabelling the median is **3.99×** (range 2.00–4.84×), and the star is cheaper on *heavy-hex* in **22 of 24** relabellings.

That number is now reported as an artifact of labelling, not as a property of connectivity.

**Reporting a result the control overturned is the point of running one.**

---

## Gate Count Expands Too — But Not In Step

![Two-qubit gate-count penalty](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig3_two_qubit_count_penalty.png)

Pooled two-qubit **count** penalties are **2.459×** for the line and **2.522×** for heavy-hex, against depth penalties of 2.691× and 2.909×.

Depth grows faster than count: some inserted SWAPs cannot be parallelized, so they land on the critical path rather than filling idle slots.

---

## What We Found

**01 — Connectivity costs depth**
Median **2.140×** on the line and **2.304×** on heavy-hex at levels 1 and 3. Including the confounded level-0 stratum, 2.691× and 2.909×.

**02 — Circuit structure dominates**
GHZ chain stays at exactly **1.000×** on both maps, while the QFT / EfficientSU2 ordering reverses on identical hardware.

**03 — Optimization pays for itself**
Level 3 roughly halves the penalty against level 0, at about 5× the compile time.

**04 — Routing is stochastic**
Five seeds on one configuration span **5.419× to 7.527×**.

**05 — Labelling is a confound, and it is measurable**
Relabelling the same graph moves level-0 results by up to **15.70×**.

**06 — And one claim did not survive**
GHZ star on the line at level 3: **1.87×** under this labelling, **3.99×** under relabelling.

---

## Methodological Integrity

**This study evaluates compiler output under modeled connectivity constraints. It does not measure physical QPU fidelity and does not demonstrate quantum advantage.**

**Level 0 measures labelling, not connectivity.** It is a declared Qiskit preset and no stored value is changed, but it pins the layout to the identity permutation, so it measures numbering as much as connectivity. Every topology claim in this deck excludes it.

The interpretation throughout is *interaction-to-coupling compatibility under a chosen layout*. Routing is required when the current placement does not map an interaction onto an allowed edge; a different layout may remove an apparent mismatch.

---

## Limitations

- Compiler-level study, not physical hardware execution
- **One graph per topology class** — heavy-hex results are Cairo's specific 27-node graph, so "heavy-hex" and "this graph" cannot be separated
- One compiler and one version: Qiskit 2.5.1 with SABRE. The routing heuristic is part of what is measured
- Depends on the tested circuit families, sizes, and the optimization set {0, 1, 3}
- Five transpiler seeds and 24 relabellings characterize, but do not exhaust, either space
- Compilation runtime is machine- and process-specific

---

## Reproducible Benchmark

![Repository QR code](https://raw.githubusercontent.com/auyjos/quantum-routing-overhead/master/output/gamma-assets/fig9_repository_qr.png)

**github.com/auyjos/quantum-routing-overhead**

Python 3.12 · Qiskit 2.5.1 · fixed transpiler seeds 11, 22, 33, 44, 55 · locked dependencies · saved raw and summary results.

Recompiling all 1,080 canonical points reproduced the stored metrics **exactly, 1,080 of 1,080**. Label-permutation conditions derive from a SHA-256 keystream, pinned by digest in the test suite.
