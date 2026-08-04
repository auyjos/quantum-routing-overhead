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
