from pathlib import Path

import pytest

from core.engine import compute_snapshot, hashable_inputs
from core.policy import load_policy


@pytest.fixture(scope="module")
def policy():
    return load_policy()


def _draft(likelihood: int, impact: int, reversibility: str = "Partially reversible"):
    return {
        "anchor": {"name": "case", "owner": "hoda"},
        "definition": {"event": "supplier fails"},
        "likelihood": {"raw_value": likelihood, "basis": "Expert judgement", "confidence": 3, "signals": []},
        "impact": {
            "raw_value": impact,
            "domains": ["Operational"],
            "reversibility": reversibility,
            "acceptability_hint": "Tolerable",
            "worst_credible_outcome": "line stops",
            "confidence": 3,
        },
    }


def test_normalisation_spans_the_full_range(policy):
    assert policy.normalise_likelihood(1) == 0.0
    assert policy.normalise_likelihood(5) == 1.0
    assert policy.normalise_impact(3) == 0.5


def test_out_of_range_values_are_clamped(policy):
    assert policy.normalise_likelihood(0) == 0.0
    assert policy.normalise_likelihood(99) == 1.0


def test_categories_match_the_documented_thresholds(policy):
    assert policy.classify(0.19) == "low"
    assert policy.classify(0.2) == "medium"
    assert policy.classify(0.5) == "high"
    assert policy.classify(0.8) == "critical"


def test_score_is_deterministic(policy):
    first = compute_snapshot(_draft(4, 4), policy)
    second = compute_snapshot(_draft(4, 4), policy)
    assert first.overall_risk_score == second.overall_risk_score
    assert first.inputs_hash == second.inputs_hash


def test_hash_ignores_derived_values(policy):
    base = _draft(4, 4)
    derived = _draft(4, 4)
    derived["likelihood"]["normalised"] = 0.75
    derived["impact"]["normalised"] = 0.75
    assert hashable_inputs(base) == hashable_inputs(derived)


def test_hash_changes_when_an_input_changes(policy):
    assert compute_snapshot(_draft(4, 4), policy).inputs_hash != compute_snapshot(_draft(5, 4), policy).inputs_hash


def test_catastrophic_impact_cannot_be_classified_low(policy):
    snapshot = compute_snapshot(_draft(1, 5), policy)
    assert snapshot.overall_risk_score == 0.0
    assert snapshot.risk_category == "high"
    assert snapshot.recommended_decision.value == "REDUCE"
    assert "catastrophic_impact" in snapshot.applied_overrides


def test_irreversible_impact_cannot_be_classified_low(policy):
    snapshot = compute_snapshot(_draft(1, 2, reversibility="Irreversible"), policy)
    assert snapshot.risk_category == "medium"
    assert snapshot.escalation_required is True


def test_low_risk_stays_low(policy):
    snapshot = compute_snapshot(_draft(2, 2), policy)
    assert snapshot.risk_category == "low"
    assert snapshot.recommended_decision.value == "ACCEPT"
    assert snapshot.applied_overrides == []


def test_snapshot_records_the_policy_version(policy):
    assert compute_snapshot(_draft(3, 3), policy).policy_version == policy.policy_version


def test_invalid_policy_is_rejected(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"scales": {}, "scoring": {}, "thresholds": {}, "decision_policy": {}}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_policy(bad)
