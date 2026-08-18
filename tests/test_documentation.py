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


def test_level_zero_is_not_softened_back_to_partly_confounded():
    """The label-permutation control superseded the original hedge.

    The control showed the identity labelling is the most favourable of all labelings
    tested at L0 (random-relabelling pooled medians 11.3x line / 6.1x Cairo against
    identity's 3.904x / 4.282x). After that measurement, describing L0 as only "partly"
    measuring index alignment, or letting an L0 number carry a topology claim, would be
    a regression. Applies to the poster, where the control is reported.
    """
    document = POSTER.read_text(encoding="utf-8")
    assert "label-permutation control" in document
    assert "partly measures index" not in document
    assert "measures labelling, not" in document


def test_the_star_line_number_is_flagged_as_labelling_dependent():
    """Identity coincides with the best case of the star's relabelling distribution."""
    document = POSTER.read_text(encoding="utf-8")
    assert "labelling-dependent" in document
    assert "19 of 24" in document


def test_the_reversal_is_reported_with_its_label_robustness():
    """QFT/Efficient SU(2) ordering held in every random relabelling tested."""
    document = POSTER.read_text(encoding="utf-8")
    assert "24 of 24" in document


def test_the_control_runs_declare_their_qiskit_version():
    """Control numbers come from 2.5.2 runs, not the canonical 2.5.1 environment."""
    document = POSTER.read_text(encoding="utf-8")
    assert "2.5.2" in document


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
