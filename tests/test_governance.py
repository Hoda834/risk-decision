"""Governance controls that were config-only before.

The authority matrix, the acceptance constraints and the inputs hash all existed
in config or in the record and nothing read them. These tests hold them to doing
something.
"""

import json
from pathlib import Path

import pytest

from core.engine import compute_snapshot
from core.integrity import check_case, snapshot_matches_inputs
from core.policy import load_policy
from core.storage import (
    LockedVersionError,
    StoragePaths,
    append_audit,
    read_audit,
    verify_audit_log,
    write_draft,
)
from core.wizard import compute_and_lock_snapshot, initial_payload, suggested_review_date


@pytest.fixture(scope="module")
def policy():
    return load_policy()


def _draft(likelihood: int, impact: int, **impact_fields):
    impact_block = {
        "raw_value": impact,
        "domains": ["Safety"],
        "reversibility": "Partially reversible",
        "acceptability_hint": "Tolerable",
        "worst_credible_outcome": "a patient is misdiagnosed",
        "confidence": 3,
    }
    impact_block.update(impact_fields)
    return {
        "anchor": {"name": "case", "owner": "hoda"},
        "definition": {"event": "the assay reads high", "consequences": "treatment is withheld"},
        "likelihood": {"raw_value": likelihood, "basis": "Expert judgement", "confidence": 3, "signals": []},
        "impact": impact_block,
    }


# ------------------------------------------------------------------- authority


def test_authority_ceilings_are_enforced(policy):
    assert policy.can_accept("risk_owner", "low")
    assert not policy.can_accept("risk_owner", "medium")
    assert policy.can_accept("management", "high")
    assert not policy.can_accept("security_lead", "high")


def test_nobody_may_accept_a_critical_risk(policy):
    assert policy.roles_that_can_accept("critical") == []


def test_a_role_above_the_hard_block_is_rejected_on_load(tmp_path: Path, policy):
    raw = json.loads(json.dumps(policy.raw))
    raw["escalation"]["authority_matrix"].append(
        {"role": "board", "max_category_to_accept": "critical"}
    )

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="hard block forbids"):
        load_policy(bad)


def test_the_snapshot_names_who_may_accept(policy):
    snapshot = compute_snapshot(_draft(4, 4), policy)
    assert snapshot.roles_that_may_accept == ["management", "executive_sponsor"]


# ------------------------------------------------------------------ acceptance


def test_an_outcome_marked_not_acceptable_blocks_acceptance(policy):
    snapshot = compute_snapshot(_draft(1, 1, acceptability_hint="Not acceptable"), policy)

    assert snapshot.risk_category == "low"
    assert snapshot.accept_blockers
    assert "Not acceptable" in snapshot.accept_blockers[0]


def test_a_critical_risk_cannot_be_accepted(policy):
    snapshot = compute_snapshot(_draft(5, 5), policy)
    assert snapshot.accept_blockers
    assert snapshot.roles_that_may_accept == []


# ------------------------------------------------------------------ escalation


def test_weak_confidence_escalates_without_changing_the_category(policy):
    confident = compute_snapshot(_draft(2, 2), policy)
    unsure = compute_snapshot(_draft(2, 2, confidence=2), policy)

    assert confident.escalation_required is False
    assert unsure.escalation_required is True
    assert unsure.risk_category == confident.risk_category
    assert "Confidence" in unsure.escalation_reasons[0]


def test_privacy_keywords_escalate_without_floring_the_category(policy):
    payload = _draft(1, 1)
    payload["definition"]["consequences"] = "location data for children is exposed"
    snapshot = compute_snapshot(payload, policy)

    assert "privacy_signal" in snapshot.applied_overrides
    assert snapshot.risk_category == "low"
    assert snapshot.escalation_required is True


def test_every_escalation_carries_a_stated_reason(policy):
    snapshot = compute_snapshot(_draft(5, 4), policy)
    assert snapshot.escalation_required
    assert all(reason.strip() for reason in snapshot.escalation_reasons)


# ------------------------------------------------------------------- integrity


def test_editing_a_locked_case_breaks_the_recorded_hash(policy):
    payload = compute_and_lock_snapshot(_locked_payload(policy), policy)
    assert snapshot_matches_inputs(payload)

    payload["impact"]["raw_value"] = 1
    assert not snapshot_matches_inputs(payload)


def test_check_case_reports_the_edit(tmp_path, policy):
    paths = StoragePaths(tmp_path)
    payload = compute_and_lock_snapshot(_locked_payload(policy), policy)
    payload["likelihood"]["raw_value"] = 1

    problems = check_case(paths, payload)
    assert any("no longer match the hash" in p for p in problems)


def test_a_locked_version_refuses_an_input_change(tmp_path, policy):
    paths = StoragePaths(tmp_path)
    payload = compute_and_lock_snapshot(_locked_payload(policy), policy)
    write_draft(paths, payload["case_id"], 1, payload)

    payload["impact"]["raw_value"] = 2
    with pytest.raises(LockedVersionError):
        write_draft(paths, payload["case_id"], 1, payload)


def test_a_locked_version_still_accepts_a_decision_change(tmp_path, policy):
    paths = StoragePaths(tmp_path)
    payload = compute_and_lock_snapshot(_locked_payload(policy), policy)
    write_draft(paths, payload["case_id"], 1, payload)

    payload["decision"]["override_note"] = "Accepted for a two week pilot."
    write_draft(paths, payload["case_id"], 1, payload)


# ------------------------------------------------------------------ audit chain


def test_the_audit_log_chains_its_entries(tmp_path):
    paths = StoragePaths(tmp_path)
    append_audit(paths, "case1", {"action": "new_case"})
    append_audit(paths, "case1", {"action": "evaluate"})

    entries = read_audit(paths, "case1")
    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]
    assert verify_audit_log(paths, "case1") is None


def test_an_edited_audit_entry_breaks_the_chain(tmp_path):
    paths = StoragePaths(tmp_path)
    for action in ("new_case", "evaluate", "decision_recorded"):
        append_audit(paths, "case1", {"action": action})

    entries = read_audit(paths, "case1")
    entries[1]["action"] = "quietly_changed"
    paths.case_audit_path("case1").write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )

    assert verify_audit_log(paths, "case1") == 1


def test_a_removed_audit_entry_breaks_the_chain(tmp_path):
    paths = StoragePaths(tmp_path)
    for action in ("new_case", "evaluate", "decision_recorded"):
        append_audit(paths, "case1", {"action": action})

    entries = read_audit(paths, "case1")
    del entries[1]
    paths.case_audit_path("case1").write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )

    assert verify_audit_log(paths, "case1") == 1


# ----------------------------------------------------------------- review date


def test_the_review_date_follows_the_time_to_impact(policy):
    soon = initial_payload(policy)
    soon["definition"]["time_to_impact_months"] = 2

    later = initial_payload(policy)
    later["definition"]["time_to_impact_months"] = 24

    assert suggested_review_date(soon) < suggested_review_date(later)


def _locked_payload(policy):
    payload = initial_payload(policy)
    payload["anchor"].update(
        {"name": "Reagent supplier failure", "owner": "Hoda", "value_statement": "Assay availability."}
    )
    payload["definition"].update(
        {
            "event": "The sole reagent supplier stops delivering.",
            "triggers": ["insolvency"],
            "cause_categories": ["Supplier"],
            "vulnerability": "No second source.",
            "consequences": "Production halts.",
            "time_to_impact_months": 3,
            "scope": "Cartridge line.",
            "assumptions": "Contract unchanged.",
            "data_used": "Supplier audit.",
            "references": "QMS-014.",
        }
    )
    payload["likelihood"]["raw_value"] = 4
    payload["impact"].update({"raw_value": 4, "domains": ["Operational"], "worst_credible_outcome": "Halt."})
    return payload
