"""Validated experiment configuration.

The YAML file is the single source of truth for the grid and for the controlled
basis; no module is allowed to hardcode its own copy of those values.
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass
from pathlib import Path

import yaml

from routing_overhead.circuits import CIRCUIT_FAMILIES
from routing_overhead.topologies import PHYSICAL_QUBITS, TOPOLOGIES
from routing_overhead.transpilation import BASIS_GATES

REQUIRED_KEYS = (
    "physical_qubits",
    "logical_qubits",
    "circuit_families",
    "topologies",
    "optimization_levels",
    "transpiler_seeds",
    "basis_gates",
)

SUPPORTED_OPTIMIZATION_LEVELS = (0, 1, 2, 3)


class ConfigError(ValueError):
    """Raised for any unusable configuration file."""


@dataclass(frozen=True)
class ExperimentConfig:
    physical_qubits: int
    logical_qubits: tuple[int, ...]
    circuit_families: tuple[str, ...]
    topologies: tuple[str, ...]
    optimization_levels: tuple[int, ...]
    transpiler_seeds: tuple[int, ...]
    basis_gates: tuple[str, ...]

    @property
    def basis_hash(self) -> str:
        return basis_hash(self.basis_gates)

    def as_dict(self) -> dict:
        return {
            "physical_qubits": self.physical_qubits,
            "logical_qubits": list(self.logical_qubits),
            "circuit_families": list(self.circuit_families),
            "topologies": list(self.topologies),
            "optimization_levels": list(self.optimization_levels),
            "transpiler_seeds": list(self.transpiler_seeds),
            "basis_gates": list(self.basis_gates),
        }

    def size(self) -> int:
        return (
            len(self.logical_qubits)
            * len(self.circuit_families)
            * len(self.topologies)
            * len(self.optimization_levels)
            * len(self.transpiler_seeds)
        )


def basis_hash(basis_gates) -> str:
    """SHA-256 over the sorted basis, so the key is independent of listing order."""
    return hashlib.sha256(",".join(sorted(basis_gates)).encode("utf-8")).hexdigest()


def load_config(path) -> ExperimentConfig:
    """Load and fully validate an experiment configuration file."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"configuration file not found: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigError(f"configuration file is not valid YAML: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ConfigError(f"configuration must be a YAML mapping, got {type(payload).__name__}")

    missing = [key for key in REQUIRED_KEYS if key not in payload]
    if missing:
        raise ConfigError(f"configuration is missing required keys: {sorted(missing)}")
    unknown = [key for key in payload if key not in REQUIRED_KEYS]
    if unknown:
        raise ConfigError(f"configuration has unknown keys: {sorted(unknown)}")

    physical_qubits = payload["physical_qubits"]
    if physical_qubits != PHYSICAL_QUBITS:
        raise ConfigError(
            f"physical_qubits must be {PHYSICAL_QUBITS} for this controlled study, "
            f"got {physical_qubits!r}"
        )

    logical_qubits = _int_list(payload, "logical_qubits")
    out_of_range = [n for n in logical_qubits if n < 2 or n > physical_qubits]
    if out_of_range:
        raise ConfigError(
            f"logical_qubits must each be between 2 and {physical_qubits}, got {out_of_range}"
        )

    optimization_levels = _int_list(payload, "optimization_levels")
    unsupported = [
        level for level in optimization_levels if level not in SUPPORTED_OPTIMIZATION_LEVELS
    ]
    if unsupported:
        raise ConfigError(
            f"optimization_levels must be within {list(SUPPORTED_OPTIMIZATION_LEVELS)}, "
            f"got {unsupported}"
        )

    return ExperimentConfig(
        physical_qubits=physical_qubits,
        logical_qubits=tuple(logical_qubits),
        circuit_families=tuple(_choice_list(payload, "circuit_families", CIRCUIT_FAMILIES)),
        topologies=tuple(_choice_list(payload, "topologies", TOPOLOGIES)),
        optimization_levels=tuple(optimization_levels),
        transpiler_seeds=tuple(_int_list(payload, "transpiler_seeds")),
        basis_gates=tuple(_controlled_basis(payload)),
    )


def experiment_grid(config: ExperimentConfig):
    """Deterministic cartesian product of the grid, one dict per transpilation."""
    for family, num_qubits, topology, level, seed in itertools.product(
        config.circuit_families,
        config.logical_qubits,
        config.topologies,
        config.optimization_levels,
        config.transpiler_seeds,
    ):
        yield {
            "circuit_family": family,
            "logical_qubits": num_qubits,
            "topology": topology,
            "optimization_level": level,
            "transpiler_seed": seed,
        }


def _sequence(payload: dict, key: str) -> list:
    value = payload[key]
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{key} must be a non-empty list, got {value!r}")
    # Equality-based, not hash-based: an invalid nested value such as [[4], [4]] must
    # still produce a ConfigError rather than a TypeError out of a set comprehension.
    seen: list = []
    repeated: list = []
    for item in value:
        if any(item == other for other in seen):
            if not any(item == other for other in repeated):
                repeated.append(item)
        else:
            seen.append(item)
    if repeated:
        # A repeated value collapses silently: both copies produce the same experiment key,
        # so the grid reports a planned run that is immediately skipped as already done.
        raise ConfigError(f"{key} contains duplicate values {repeated!r}")
    return value


def _int_list(payload: dict, key: str) -> list[int]:
    values = _sequence(payload, key)
    bad = [value for value in values if not isinstance(value, int) or isinstance(value, bool)]
    if bad:
        raise ConfigError(f"{key} must contain integers, got {bad!r}")
    return values


def _controlled_basis(payload: dict) -> list[str]:
    """The study fixes one shared basis; a subset or reordering is a methodology change."""
    values = _sequence(payload, "basis_gates")
    if tuple(values) != tuple(BASIS_GATES):
        raise ConfigError(
            f"basis_gates must be exactly {list(BASIS_GATES)} for this controlled study, "
            f"got {values!r}"
        )
    return values


def _choice_list(payload: dict, key: str, allowed) -> list[str]:
    values = _sequence(payload, key)
    bad = [value for value in values if value not in allowed]
    if bad:
        raise ConfigError(f"{key} contains unsupported values {bad!r}; allowed: {list(allowed)}")
    return values
