"""The matrix replaces arithmetic on ordinal labels.

Likelihood and impact are labels, so the distance between two points is not
defined and their product carries no meaning. Every cell is a stated decision,
and these tests hold the grid to the properties that make it defensible.
"""

import json
from pathlib import Path

import pytest

from core.engine import compute_snapshot
from core.policy import load_policy


@pytest.fixture(scope="module")
def policy():
    return load_policy()


def _draft(likelihood: int, impact: int, **impact_fields):
    impact_block = {
        "raw_value": impact,
        "domains": ["Operational"],
        "reversibility": "Partially reversible",
        "acceptability_hint": "Tolerable",
        "worst_credible_outcome": "line stops",
        "confidence": 3,
    }
    impact_block.update(impact_fields)
    return {
        "anchor": {"name": "case", "owner": "hoda"},
        "definition": {"event": "supplier fails"},
        "likelihood": {"raw_value": likelihood, "basis": "Expert judgement", "confidence": 3, "signals": []},
        "impact": impact_block,
    }


def _grid(policy):
    return {
        (likelihood, impact): policy.category_from_matrix(likelihood, impact)
        for likelihood in policy.scale_points("likelihood")
        for impact in policy.scale_points("impact")
    }


def test_no_cell_scores_a_risk_out_of_existence(policy):
    """The old formula zeroed 9 of 25 cells. A 1 on either axis wiped the other."""
    for (likelihood, impact), category in _grid(policy).items():
        if likelihood > 1 and impact >= 4:
            assert category != "low", (likelihood, impact)


def test_a_major_impact_is_never_accepted_by_default(policy):
    for likelihood in policy.scale_points("likelihood"):
        for impact in (4, 5):
            snapshot = compute_snapshot(_draft(likelihood, impact), policy)
            assert snapshot.recommended_decision.value != "ACCEPT", (likelihood, impact)


def test_the_matrix_is_monotonic_in_both_directions(policy):
    grid = _grid(policy)
    rank = policy.category_rank

    for likelihood in policy.scale_points("likelihood"):
        row = [rank(grid[(likelihood, i)]) for i in policy.scale_points("impact")]
        assert row == sorted(row), likelihood

    for impact in policy.scale_points("impact"):
        column = [rank(grid[(l, impact)]) for l in policy.scale_points("likelihood")]
        assert column == sorted(column), impact


def test_a_non_monotonic_matrix_is_rejected_on_load(tmp_path: Path, policy):
    raw = json.loads(json.dumps(policy.raw))
    raw["scoring"]["category_matrix"]["cells"]["3"] = ["low", "medium", "medium", "low", "critical"]

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="monotonic"):
        load_policy(bad)


def test_a_matrix_with_a_missing_row_is_rejected_on_load(tmp_path: Path, policy):
    raw = json.loads(json.dumps(policy.raw))
    del raw["scoring"]["category_matrix"]["cells"]["5"]

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="one row per likelihood point"):
        load_policy(bad)


def test_the_ordering_score_ranks_without_classifying(policy):
    rare_catastrophic = compute_snapshot(_draft(1, 5), policy)
    likely_moderate = compute_snapshot(_draft(4, 3), policy)

    assert rare_catastrophic.overall_risk_score < likely_moderate.overall_risk_score
    assert policy.category_rank(rare_catastrophic.risk_category) >= policy.category_rank(
        likely_moderate.risk_category
    )


def test_overrides_still_raise_the_matrix_result(policy):
    plain = compute_snapshot(_draft(1, 2), policy)
    irreversible = compute_snapshot(_draft(1, 2, reversibility="Irreversible"), policy)

    assert plain.risk_category == "low"
    assert irreversible.risk_category == "medium"
    assert irreversible.matrix_category == "low"
