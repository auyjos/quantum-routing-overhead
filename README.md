# Quantum Routing Overhead

Controlled benchmark of how complete, line, and Cairo heavy-hex connectivity affect
Qiskit circuit compilation.

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

## Poster figures

`plot` draws the poster figure set as PNG (300 dpi) and SVG into `<run>/figures/`.
Compilation-time figures need the process repeats; pass each repeat run directory
with `--timing-run`. A repeat that does not reproduce the canonical run's non-time
outputs exactly is rejected instead of pooled.

```powershell
python -m routing_overhead.cli aggregate --run artifacts/runs/stage3-core-a2899b8e
python -m routing_overhead.cli plot --run artifacts/runs/stage3-core-a2899b8e `
  --timing-run artifacts/runs/stage3-timing-r2-lhc-a2899b8e `
  --timing-run artifacts/runs/stage3-timing-r3-hcl-a2899b8e
```
