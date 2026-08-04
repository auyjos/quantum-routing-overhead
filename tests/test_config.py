"""Stage 2 tests for validated experiment configuration loading."""

import dataclasses
from pathlib import Path

import pytest
import yaml

from routing_overhead.config import ConfigError, basis_hash, experiment_grid, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]

VALID = {
    "physical_qubits": 27,
    "logical_qubits": [4, 8],
    "circuit_families": ["ghz_chain", "ghz_star"],
    "topologies": ["complete_27", "line_27"],
    "optimization_levels": [1],
    "transpiler_seeds": [11, 22],
    "basis_gates": ["rz", "sx", "x", "cx"],
}


def write_config(tmp_path, **overrides):
    payload = {**VALID, **overrides}
    for key, value in list(payload.items()):
        if value is None:
            del payload[key]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_shipped_smoke_config_loads():
    config = load_config(REPO_ROOT / "configs" / "smoke.yaml")
    assert config.logical_qubits == (4, 8)
    assert config.circuit_families == ("ghz_chain", "ghz_star")
    assert config.topologies == ("complete_27", "line_27")
    assert config.optimization_levels == (1,)
    assert config.transpiler_seeds == (11, 22)
    assert config.basis_gates == ("rz", "sx", "x", "cx")


def test_shipped_core_config_loads():
    config = load_config(REPO_ROOT / "configs" / "core.yaml")
    assert config.logical_qubits == (4, 8, 12, 16, 20, 24)
    assert len(config.circuit_families) == 4
    assert len(config.topologies) == 3


def test_config_is_immutable(tmp_path):
    config = load_config(write_config(tmp_path))
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.physical_qubits = 5


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "absent.yaml")


@pytest.mark.parametrize(
    "key",
    [
        "physical_qubits",
        "logical_qubits",
        "circuit_families",
        "topologies",
        "optimization_levels",
        "transpiler_seeds",
        "basis_gates",
    ],
)
def test_missing_key_is_rejected(tmp_path, key):
    with pytest.raises(ConfigError, match="missing"):
        load_config(write_config(tmp_path, **{key: None}))


def test_unknown_key_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="unknown"):
        load_config(write_config(tmp_path, worker_count=4))


def test_unknown_circuit_family_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="circuit_families"):
        load_config(write_config(tmp_path, circuit_families=["ghz_chain", "random"]))


def test_unknown_topology_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="topologies"):
        load_config(write_config(tmp_path, topologies=["ring_27"]))


def test_physical_qubit_count_must_match_the_controlled_device_size(tmp_path):
    with pytest.raises(ConfigError, match="physical_qubits"):
        load_config(write_config(tmp_path, physical_qubits=16))


def test_logical_qubits_may_not_exceed_the_device(tmp_path):
    with pytest.raises(ConfigError, match="logical_qubits"):
        load_config(write_config(tmp_path, logical_qubits=[4, 28]))


def test_logical_qubits_must_be_at_least_two(tmp_path):
    with pytest.raises(ConfigError, match="logical_qubits"):
        load_config(write_config(tmp_path, logical_qubits=[1]))


def test_optimization_levels_are_restricted(tmp_path):
    with pytest.raises(ConfigError, match="optimization_levels"):
        load_config(write_config(tmp_path, optimization_levels=[0, 4]))


def test_empty_list_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="transpiler_seeds"):
        load_config(write_config(tmp_path, transpiler_seeds=[]))


def test_non_integer_seed_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="transpiler_seeds"):
        load_config(write_config(tmp_path, transpiler_seeds=["eleven"]))


def test_unsupported_basis_gate_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="basis_gates"):
        load_config(write_config(tmp_path, basis_gates=["rz", "sx", "x", 7]))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("logical_qubits", [4, 4]),
        ("circuit_families", ["ghz_chain", "ghz_chain"]),
        ("topologies", ["line_27", "complete_27", "line_27"]),
        ("optimization_levels", [1, 1]),
        ("transpiler_seeds", [11, 22, 11]),
        ("basis_gates", ["rz", "sx", "x", "cx", "cx"]),
    ],
)
def test_duplicate_grid_values_are_rejected(tmp_path, key, value):
    with pytest.raises(ConfigError, match="duplicate"):
        load_config(write_config(tmp_path, **{key: value}))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("logical_qubits", [[4], [4]]),
        ("logical_qubits", [{"n": 4}]),
        ("transpiler_seeds", [[11, 22]]),
        ("circuit_families", [["ghz_chain"]]),
    ],
)
def test_unhashable_axis_values_raise_a_configuration_error(tmp_path, key, value):
    with pytest.raises(ConfigError):
        load_config(write_config(tmp_path, **{key: value}))


def test_basis_must_be_the_exact_controlled_set(tmp_path):
    with pytest.raises(ConfigError, match="basis_gates"):
        load_config(write_config(tmp_path, basis_gates=["cx"]))


def test_basis_missing_a_gate_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="basis_gates"):
        load_config(write_config(tmp_path, basis_gates=["rz", "sx", "x"]))


def test_basis_in_a_different_order_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="basis_gates"):
        load_config(write_config(tmp_path, basis_gates=["cx", "x", "sx", "rz"]))


def test_basis_hash_is_order_independent_and_stable():
    assert basis_hash(("rz", "sx", "x", "cx")) == basis_hash(("cx", "x", "sx", "rz"))
    assert basis_hash(("rz", "sx", "x", "cx")) != basis_hash(("rz", "sx", "x", "cz"))
    assert len(basis_hash(("rz", "sx", "x", "cx"))) == 64


def test_experiment_grid_is_the_full_cartesian_product(tmp_path):
    config = load_config(write_config(tmp_path))
    grid = list(experiment_grid(config))
    assert len(grid) == 2 * 2 * 2 * 1 * 2
    assert len({tuple(sorted(point.items())) for point in grid}) == len(grid)
    assert set(grid[0]) == {
        "circuit_family",
        "logical_qubits",
        "topology",
        "optimization_level",
        "transpiler_seed",
    }


def test_experiment_grid_order_is_deterministic(tmp_path):
    config = load_config(write_config(tmp_path))
    assert list(experiment_grid(config)) == list(experiment_grid(config))
