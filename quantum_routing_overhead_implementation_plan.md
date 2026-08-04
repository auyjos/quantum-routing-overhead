# Implementation Plan — Quantum Routing Overhead

## Project

**Title:** Quantifying Routing Overhead in Quantum Circuit Compilation: A Controlled Comparison of Hardware Topologies

**Goal:** Measure how restricted qubit connectivity changes compiled circuit depth, two-qubit depth, two-qubit gate count, and compilation time.

**Core comparison:** Compile identical circuits under three 27-qubit connectivity models while holding the gate basis and compiler settings constant:

1. Complete connectivity
2. Linear connectivity
3. IBM Cairo heavy-hex connectivity

This is a compiler benchmark. It does not require quantum hardware or quantum-state simulation.

---

## 1. Research Questions

### Primary

How much do linear and heavy-hex connectivity increase two-qubit depth relative to complete connectivity?

### Secondary

- Which circuit interaction patterns are most affected?
- How much do Qiskit optimization levels reduce routing overhead?
- How much do results vary across transpiler seeds?
- What compilation-time cost accompanies stronger optimization?

### Expected result

Complete connectivity should have the lowest routing overhead. Linear connectivity should generally have the largest penalty, especially for dense or star-shaped interaction patterns. Heavy-hex should usually fall between them.

Do not assume every individual run will follow this ordering. Report the data.

---

## 2. Scope

### Required

- 27 physical qubits for every topology
- Four circuit families
- Logical sizes: `4, 8, 12, 16, 20, 24`
- Optimization levels: `0, 1, 3`
- Five transpiler seeds
- Shared native basis
- Raw results saved per transpilation
- Reproducible configuration files
- Automated tests
- Poster-ready figures

### Optional only after the core study works

- Ten transpiler seeds
- Optimization level 2
- Random circuits
- 127-qubit heavy-hex comparison
- Exact routing for four or five qubits
- Hardware-aware gate-duration analysis
- Real-device execution

Do not add optional work before the core experiment is complete.

---

## 3. Methodological Rules

1. **Change one major factor at a time.**
   In the main experiment, change connectivity only. Keep physical-qubit count, gate basis, circuit, optimization level, and seed fixed.

2. **Use a common basis.**
   Suggested controlled basis:

   ```python
   BASIS_GATES = ["rz", "sx", "x", "cx"]
   ```

   Confirm that the installed Qiskit version supports this configuration before starting the full run.

3. **Do not compare a full backend target directly against generic coupling maps in the primary experiment.**
   A backend target may include native gates, directionality, durations, and device properties. That would confound topology with hardware configuration.

4. **Treat the Cairo backend only as the source of the heavy-hex coupling graph.**

5. **Use identical circuit instances across topologies.**

6. **Use identical transpiler seeds across topologies.**

7. **Save all runs, including failures.**

8. **Do not report only the best seed.**
   Headline results should use the median and interquartile range. Mean and standard deviation may be included as secondary summaries.

9. **Do not infer routing SWAP count by dividing extra CX gates by three.**
   Optimizations and decompositions can invalidate that assumption.

10. **Do not claim quantum advantage or hardware performance.**
    This study measures compiler output under modeled connectivity.

---

## 4. Technology

### Runtime

- Python 3.11 or 3.12
- Use the newest version supported by the selected Qiskit release
- Record the actual Python version

### Dependencies

```text
qiskit
qiskit-ibm-runtime
numpy
pandas
pyarrow
matplotlib
pyyaml
networkx
pytest
ruff
```

Optional:

```text
jupyter
mypy
```

### Version policy

1. Create the environment.
2. Implement the smoke test.
3. Confirm the Qiskit APIs work.
4. Freeze exact dependency versions.
5. Do not upgrade during data collection.

```bash
python -m pip freeze > requirements.lock.txt
```

---

## 5. Repository Structure

```text
quantum-routing-overhead/
├── README.md
├── pyproject.toml
├── requirements.lock.txt
├── configs/
│   ├── smoke.yaml
│   ├── core.yaml
│   └── extended.yaml
├── src/
│   └── routing_overhead/
│       ├── __init__.py
│       ├── config.py
│       ├── circuits.py
│       ├── topologies.py
│       ├── transpilation.py
│       ├── metrics.py
│       ├── experiments.py
│       ├── aggregation.py
│       ├── plotting.py
│       └── cli.py
├── tests/
│   ├── test_circuits.py
│   ├── test_topologies.py
│   ├── test_metrics.py
│   ├── test_transpilation.py
│   └── test_smoke.py
├── artifacts/
│   └── runs/
├── notebooks/
│   └── results_analysis.ipynb
└── poster/
    ├── figures/
    └── poster-content.md
```

### Rules

- Production logic belongs under `src/`.
- Notebooks are for exploration only.
- Every experiment must run from the CLI.
- Configuration values must not be hardcoded across modules.

---

## 6. Circuit Families

Each builder returns a `QuantumCircuit` and accepts a logical-qubit count.

### 6.1 QFT

Use the current Qiskit synthesis function rather than deprecated QFT circuit classes.

```python
from qiskit.synthesis import synth_qft_full

circuit = synth_qft_full(
    num_qubits=n,
    do_swaps=False,
)
```

Use `do_swaps=False` to omit the final output-reversal network. This avoids mixing algorithm-level final SWAPs with routing overhead. Document this decision in the paper and poster.

### 6.2 GHZ chain

```text
H(0)
CX(0, 1)
CX(1, 2)
...
CX(n-2, n-1)
```

This interaction pattern is naturally compatible with a line.

### 6.3 GHZ star

```text
H(0)
CX(0, 1)
CX(0, 2)
...
CX(0, n-1)
```

This prepares a GHZ state using a high-degree logical interaction pattern. It should expose connectivity limitations clearly.

### 6.4 Hardware-efficient ansatz

Use the function API:

```python
from qiskit.circuit.library import efficient_su2

circuit = efficient_su2(
    num_qubits=n,
    entanglement="circular",
    reps=2,
)
```

Bind parameters before metrics or transpilation when required:

```python
values = {parameter: 0.5 for parameter in circuit.parameters}
circuit = circuit.assign_parameters(values)
```

Use fixed parameter values because the study concerns topology and compilation, not optimization of variational parameters.

### Circuit metadata

Record for every input circuit:

- Family
- Logical qubits
- Input depth
- Input two-qubit depth
- Input operation counts
- Input two-qubit gate count
- Circuit-generation settings
- Circuit hash

Create a deterministic hash from a stable serialized representation. Use it to verify that all topologies received the same input circuit.

---

## 7. Topologies

### 7.1 Complete

```python
from qiskit.transpiler import CouplingMap

complete = CouplingMap.from_full(27, bidirectional=True)
```

### 7.2 Line

```python
line = CouplingMap.from_line(27, bidirectional=True)
```

### 7.3 Cairo heavy-hex

```python
from qiskit_ibm_runtime.fake_provider import FakeCairoV2

backend = FakeCairoV2()
heavy_hex = backend.target.build_coupling_map()
```

Validate that the returned map:

- Contains 27 physical qubits
- Is connected
- Is bidirectional for the controlled experiment, or is explicitly symmetrized
- Is saved as an edge list with the run

If directionality is removed, state that the experiment studies undirected connectivity constraints rather than calibrated directional gate support.

### Topology metadata

Record:

- Physical-qubit count
- Directed edge count
- Undirected edge count
- Minimum degree
- Maximum degree
- Mean degree
- Graph diameter
- Average shortest-path length
- Connected status
- Edge-list hash

Use NetworkX only for descriptive graph metrics. Use Qiskit's `CouplingMap` as the transpiler input.

---

## 8. Experiment Matrix

### Core grid

```yaml
logical_qubits: [4, 8, 12, 16, 20, 24]

circuit_families:
  - qft
  - ghz_chain
  - ghz_star
  - efficient_su2

topologies:
  - complete_27
  - line_27
  - cairo_heavy_hex_27

optimization_levels: [0, 1, 3]

transpiler_seeds: [11, 22, 33, 44, 55]
```

Total:

```text
6 sizes × 4 circuits × 3 topologies × 3 levels × 5 seeds
= 1,080 transpilation runs
```

### Execution strategy

Run in stages:

1. Smoke grid
2. One complete circuit family
3. All families with one seed
4. Full five-seed grid

Do not launch 1,080 runs before validating metrics and artifact storage.

### Runtime guardrail

If the projected core run exceeds the available schedule:

1. Keep all circuit families.
2. Keep all topologies.
3. Keep levels `0, 1, 3`.
4. Reduce logical sizes to `4, 8, 12, 16, 20`.
5. Reduce seeds only as the final fallback.

Multiple seeds are important because routing is stochastic.

---

## 9. Transpilation

Use `generate_preset_pass_manager`.

Conceptual implementation:

```python
from qiskit.transpiler import generate_preset_pass_manager

pass_manager = generate_preset_pass_manager(
    optimization_level=optimization_level,
    basis_gates=BASIS_GATES,
    coupling_map=coupling_map,
    seed_transpiler=transpiler_seed,
)

compiled = pass_manager.run(circuit)
```

### Per-run process

1. Build or load the exact input circuit.
2. Validate circuit hash.
3. Load the topology.
4. Start `time.perf_counter()`.
5. Create the preset pass manager.
6. Compile the circuit.
7. Stop the timer.
8. Validate the output.
9. Extract metrics.
10. Save one raw result row immediately.
11. Optionally save the compiled circuit for selected representative runs.

### Failure handling

A failed run must create a result row containing:

- Experiment key
- `success = false`
- Exception class
- Error message
- Runtime before failure
- Package versions

Never silently skip a configuration.

### Parallelism

Start sequentially.

After benchmarking:

- Use modest process-level parallelism.
- Avoid nested oversubscription.
- Record worker count and CPU information.
- Do not compare compilation runtime across runs collected under materially different load conditions.

For final timing results, use a controlled worker count, preferably one process or a fixed low number.

---

## 10. Metrics

### 10.1 Total circuit depth

```python
total_depth = circuit.depth()
```

### 10.2 Two-qubit depth

```python
def is_two_qubit(instruction) -> bool:
    return len(instruction.qubits) == 2

two_qubit_depth = circuit.depth(filter_function=is_two_qubit)
```

### 10.3 Two-qubit gate count

```python
two_qubit_count = sum(
    1 for instruction in circuit.data
    if len(instruction.qubits) == 2
)
```

This is more robust than assuming a specific two-qubit gate name.

### 10.4 Compilation time

```python
elapsed_seconds = end - start
```

Use `time.perf_counter()`.

### 10.5 Penalty ratios

Join every constrained-topology result with its matching complete-connectivity baseline using:

- Circuit family
- Logical qubits
- Optimization level
- Transpiler seed
- Circuit hash
- Shared basis

Then calculate:

```text
depth_penalty =
    constrained_total_depth / complete_total_depth

two_qubit_depth_penalty =
    constrained_two_qubit_depth / complete_two_qubit_depth

two_qubit_count_penalty =
    constrained_two_qubit_count / complete_two_qubit_count
```

### Zero denominators

Do not silently replace zero denominators.

- If both numerator and denominator are zero, mark the ratio as not applicable.
- If only the denominator is zero, flag the run for investigation.

### Primary outcome

**Two-qubit depth penalty**

This is the headline metric because two-qubit operations are central to routing and are typically more expensive than single-qubit operations.

### Summary statistics

For each configuration across seeds, calculate:

- Count
- Median
- Interquartile range
- Minimum
- Maximum
- Mean
- Standard deviation

Use median and IQR in the main figures.

---

## 11. Raw Data Schema

One row per transpilation:

```text
run_id
experiment_id
planned_point_id
timestamp_utc
circuit_family
logical_qubits
circuit_hash
circuit_settings_json
physical_qubits
topology
topology_hash
optimization_level
transpiler_seed
basis_gates
input_depth
input_two_qubit_depth
input_two_qubit_count
output_depth
output_two_qubit_depth
output_two_qubit_count
compile_time_seconds
depth_penalty
two_qubit_depth_penalty
two_qubit_count_penalty
success
exception_type
error_message
python_version
qiskit_version
qiskit_ibm_runtime_version
platform
cpu
worker_count
```

Save raw results as Parquet and CSV.

Parquet is the canonical machine-readable result. CSV is for inspection and sharing.

---

## 12. Artifact Layout

```text
artifacts/runs/<run-id>/
├── config.yaml
├── environment.json
├── topology_metadata.parquet
├── circuit_metadata.parquet
├── raw_results.parquet
├── raw_results.csv
├── summary_results.parquet
├── failures.csv
├── logs/
├── representative_circuits/
└── figures/
```

### Reproducibility requirements

Every run directory must include:

- Full configuration
- Git commit SHA
- Dirty-working-tree status
- Dependency versions
- Python version
- Operating system
- CPU model
- Start and end times
- Exact topology edge lists
- All seeds

---

## 13. CLI

Required commands:

```bash
python -m routing_overhead.cli validate-config configs/smoke.yaml
python -m routing_overhead.cli run --config configs/smoke.yaml
python -m routing_overhead.cli run --config configs/core.yaml
python -m routing_overhead.cli aggregate --run artifacts/runs/<run-id>
python -m routing_overhead.cli plot --run artifacts/runs/<run-id>
```

### CLI behavior

- Nonzero exit code on invalid configuration
- Clear progress output
- Resume support
- Skip every planned point that already has a terminal result row, whether success or failure
- Never overwrite an existing run directory
- Flush result rows after each run or small batch
- Log tracebacks to file
- Print the output directory when complete

### Resume identity

Use a deterministic `planned_point_id` available before circuit or topology construction:

```text
circuit_family
+ logical_qubits
+ topology
+ optimization_level
+ transpiler_seed
+ basis_hash
```

A saved success or failure is terminal within that run directory. Resume only executes
interrupted points with no saved row. After fixing code, configuration, dependencies, or
environment problems, start a new run directory to preserve clean provenance.

For successful construction, also retain the content-derived experiment key:

```text
circuit_hash
+ topology_hash
+ optimization_level
+ transpiler_seed
+ basis_hash
```

---

## 14. Testing

### 14.1 Circuit tests

- Correct number of logical qubits
- No measurements
- Deterministic construction
- GHZ chain has `n - 1` original CX operations
- GHZ star has `n - 1` original CX operations
- QFT uses `do_swaps=False`
- Ansatz parameters are fully bound before compilation
- Circuit hash is stable

### 14.2 Topology tests

- Complete map has 27 nodes
- Line map has 27 nodes
- Heavy-hex map has 27 nodes
- Every map is connected
- Complete map has distance 1 between distinct nodes
- Line diameter is 26
- Heavy-hex edge list is stable within the locked environment
- No topology object is mutated between runs

### 14.3 Metric tests

Use hand-built circuits with known values.

- Empty circuit depth is zero
- A single CX has two-qubit depth one
- Two parallel CX gates have two-qubit depth one
- Two sequential CX gates sharing a qubit have two-qubit depth two
- Two-qubit count counts every two-qubit instruction
- Penalty joins use the correct complete baseline
- Zero denominators are handled explicitly

### 14.4 Transpilation tests

- Output uses only allowed basis operations
- Every output two-qubit operation respects the coupling map
- Same input and seed produce the same output metrics
- Complete connectivity does not require connectivity-driven routing for simple circuits
- A nonlocal interaction on a line produces additional routing cost
- Invalid configurations create useful errors

### 14.5 Equivalence tests

For small circuits only, compare original and compiled operations while accounting for the final layout.

Limit full unitary checks to approximately five qubits because matrix size grows exponentially.

The test must verify semantic equivalence, not exact gate-by-gate equality.

### 14.6 End-to-end smoke test

Grid:

```yaml
logical_qubits: [4, 8]
circuit_families: [ghz_chain, ghz_star]
topologies: [complete_27, line_27]
optimization_levels: [1]
transpiler_seeds: [11, 22]
```

Expected runs: `16`.

Assert:

- All expected result rows exist
- No duplicate experiment keys
- Raw results save correctly
- Aggregation succeeds
- At least one plot is generated
- Environment metadata exists

---

## 15. Analysis

### Main comparisons

1. Heavy-hex versus complete
2. Line versus complete
3. GHZ chain versus GHZ star
4. Optimization level versus output quality
5. Optimization level versus compilation time
6. Seed variability by circuit and topology

### Statistical approach

This is an exploratory benchmark, not a clinical trial.

Use:

- Median and IQR
- Mean and standard deviation
- Paired differences when comparing topologies under the same circuit, level, and seed
- Effect sizes as absolute and multiplicative penalties

Avoid unnecessary significance testing with only five seeds. Emphasize effect size and consistency.

### Validation checks before conclusions

- Confirm every penalty uses the correct baseline.
- Inspect outliers manually.
- Confirm failures are not concentrated in one topology.
- Confirm input hashes match across topology comparisons.
- Confirm no package update occurred during collection.
- Rerun a representative sample from a clean environment.

---

## 16. Poster Figures

### Required

1. **Topology comparison**
   Complete, line, and Cairo heavy-hex diagrams.

2. **Two-qubit depth penalty versus logical qubits**
   Separate lines for line and heavy-hex; facet by circuit family.

3. **Two-qubit gate-count penalty versus logical qubits**

4. **GHZ chain versus GHZ star**
   This should be the most intuitive illustration.

5. **Optimization quality versus compilation time**

6. **Seed variability**
   Box plots for selected high-overhead configurations.

### Plot rules

- Generate figures from saved data.
- Do not manually enter result values.
- Include units.
- Use consistent topology and circuit labels.
- Export PNG at high resolution and SVG or PDF for poster use.
- Avoid overcrowded legends.
- Show median and IQR where appropriate.
- Do not truncate axes in a misleading way.

---

## 17. Development Schedule

### August 3–4: foundation

- Create repository
- Configure environment
- Implement circuit builders
- Implement topologies
- Implement metric functions
- Complete unit tests
- Run the 16-run smoke grid
- Freeze dependencies

**Exit criterion:** smoke grid completes reproducibly.

### August 5–7: experiment engine

- Implement configuration validation
- Implement transpilation runner
- Add artifact persistence
- Add resume support
- Add CLI
- Add integration tests
- Run one full circuit family

**Exit criterion:** interrupted runs can resume without duplication.

### August 8–10: core data collection

- Run all circuit families with one seed
- Inspect trends
- Fix methodology or bugs before scaling
- Run the full five-seed grid
- Save failures and logs

**Exit criterion:** all 1,080 configurations are completed or explicitly accounted for.

### August 11–13: validation and analysis

- Aggregate results
- Verify baseline joins
- Investigate outliers
- Reproduce selected runs
- Generate first figures
- Draft result statements

**Exit criterion:** every poster claim traces to saved data.

### August 14–17: poster

- Finalize figures
- Write methodology
- Write limitations
- Write conclusion
- Add repository QR code
- Review with an advisor or technical peer

### August 18–20: final verification

- Run clean-environment reproduction
- Proofread poster
- Export print-ready PDF
- Print a reduced-size test
- Check fonts, labels, and QR code

### August 21: print and buffer

- Print final A0 poster
- Store digital backups
- Keep one day for printing problems

---

## 18. Risks and Controls

| Risk | Control |
|---|---|
| Qiskit API changes | Lock dependencies after the smoke test |
| Full grid takes too long | Benchmark early; reduce sizes before reducing seeds |
| Incorrect baseline joins | Use hashes and strict composite keys |
| Topology comparison is confounded | Use one common basis and coupling maps only |
| Heavy-hex map changes after package update | Lock package and save edge list |
| Routing randomness is hidden | Use multiple fixed seeds |
| Runtime measurements are noisy | Fixed worker count and controlled machine load |
| QFT swaps contaminate routing | Use `do_swaps=False` and document it |
| Ansatz contains unbound parameters | Bind deterministic values before compilation |
| Failed runs disappear | Persist explicit failure rows |
| Results cannot be reproduced | Save configuration, environment, hashes, and Git state |
| Poster overclaims | State that results concern compiler output, not QPU fidelity |

---

## 19. Definition of Done

- [ ] Repository installs from a clean environment
- [ ] Dependency versions are locked
- [ ] All circuit builders are deterministic
- [ ] All topology validators pass
- [ ] Smoke experiment passes
- [ ] Core grid is completed or all failures are documented
- [ ] Raw results are saved in Parquet and CSV
- [ ] Every constrained run has the correct complete baseline
- [ ] Metrics are covered by unit tests
- [ ] Representative circuits pass equivalence checks
- [ ] Selected runs reproduce exactly
- [ ] At least five poster-ready figures exist
- [ ] Every conclusion is supported by saved results
- [ ] Limitations are explicit
- [ ] No hardware-performance or quantum-advantage claim is made
- [ ] README contains exact reproduction commands
- [ ] Final poster PDF is printed before travel

---

## 20. Immediate Next Steps

1. Create the repository and environment.
2. Implement GHZ chain and GHZ star.
3. Build complete and line coupling maps.
4. Compile a four-qubit GHZ star against both maps.
5. Verify that line connectivity produces measurable overhead.
6. Implement and test two-qubit depth.
7. Add Cairo heavy-hex connectivity.
8. Run the 16-configuration smoke grid.
9. Freeze dependencies.
10. Begin the experiment runner only after the smoke results are correct.

---

## Official Qiskit References

- Preset pass manager: https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.transpiler.generate_preset_pass_manager
- Coupling maps: https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.transpiler.CouplingMap
- Target and coupling-map extraction: https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.transpiler.Target
- QFT synthesis: https://quantum.cloud.ibm.com/docs/en/api/qiskit/synthesis
- Efficient SU(2) circuit: https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.circuit.library.efficient_su2
- QuantumCircuit metrics: https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.circuit.QuantumCircuit
- IBM fake backends: https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/fake-provider
- Fake Cairo V2: https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/fake-provider-fake-cairo-v2
