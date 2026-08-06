"""Documentation contract: the claims the results council required, checked in CI.

These are wording-level regressions, not prose review. Each assertion stands for a
correction that was agreed after the results were accepted, and that a later edit could
silently undo.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
POSTER = REPO_ROOT / "poster" / "poster-content.md"
PLOTTING = REPO_ROOT / "src" / "routing_overhead" / "plotting.py"

DOCUMENTS = (README, POSTER)


@pytest.fixture(params=DOCUMENTS, ids=lambda path: path.name)
def document(request):
    return request.param.read_text(encoding="utf-8")


def test_the_cell_tally_is_not_reported(document):
    """The L0-sensitive 35/21/16 tally must not be presented as ranking evidence."""
    assert not re.search(r"\b35\b[^.\n]{0,120}\b21\b[^.\n]{0,120}\b16\b", document)
    assert not re.search(r"binom", document, re.IGNORECASE)


def test_the_level_zero_layout_caveat_is_stated(document):
    assert "TrivialLayout" in document


def test_the_level_two_omission_is_explained(document):
    assert re.search(r"level\s*2\b", document, re.IGNORECASE)


def test_the_cairo_ghz_chain_is_reported_stratified(document):
    """The pooled 1.000x hides the L0 stratum and the n=24 structural case."""
    assert "4.026" in document
    assert "2.304" in document


def test_provenance_is_code_only(document):
    assert "code-only" in document
    assert "distributed accepted artifact bundle" not in document


def test_documented_commands_run_from_a_fresh_clone(document):
    """A clone has no `artifacts/runs`: `.gitignore` excludes it and no bundle is published."""
    assert "--run artifacts/runs/stage3-" not in document
    for config in re.findall(r"configs/[\w.-]+\.yaml", document):
        assert (REPO_ROOT / config).is_file(), config


def test_the_timing_label_rationale_matches_its_own_data():
    """Cairo's pooled median exceeds the line's at every tested level; it never flips."""
    source = PLOTTING.read_text(encoding="utf-8")
    rationale = source.split("TIMING_LABEL_OFFSETS")[0]
    assert "changes between levels" not in rationale
