"""Guards against the failure that broke this repo before.

The app and the tests were written against a version of core/ that was never
committed, so nothing caught the drift until launch. These tests import the app
and drive one full case through the public API.
"""

from typing import Any, Dict, List

import pytest

from core.models import RiskCaseDraft
from core.policy import load_policy
from core.questions import Question, load_question_bank
from core.wizard import (
    WizardStateEnum,
    apply_answer,
    compute_and_lock_snapshot,
    initial_payload,
    is_locked,
    outstanding_steps,
    questions_for_state,
    try_make_draft_model,
    validate_answer,
)


@pytest.fixture(scope="module")
def policy():
    return load_policy()


@pytest.fixture(scope="module")
def questions(policy):
    return load_question_bank(policy=policy)


def _answer_for(q: Question) -> Any:
    if q.input_type in {"text", "textarea"}:
        return "A specific and sufficiently detailed answer for this field."
    if q.input_type == "list_text":
        return "first trigger line\nsecond trigger line"
    if q.input_type == "single_select":
        return q.options[0]
    if q.input_type == "multi_select":
        return [q.options[0]]
    if q.input_type == "scale":
        return max(q.options)
    if q.input_type == "slider":
        return int((q.validation or {}).get("max", 5))
    if q.input_type == "number":
        return 6
    raise AssertionError(f"No answer strategy for {q.input_type}")


def _fill(payload: Dict[str, Any], questions: List[Question]) -> Dict[str, Any]:
    for q in questions:
        apply_answer(payload, q.path, _answer_for(q))
    return payload


def test_the_app_imports_against_the_current_core_api():
    import streamlit_app  # noqa: F401


def test_every_question_answer_passes_its_own_validation(questions):
    for q in questions:
        assert validate_answer(q, _answer_for(q)) is None, q.qid


def test_every_question_path_exists_on_the_model(policy, questions):
    payload = _fill(initial_payload(policy), questions)
    draft, err = try_make_draft_model(payload)
    assert draft is not None, err
    assert isinstance(draft, RiskCaseDraft)


def test_a_full_run_locks_and_scores(policy, questions):
    payload = _fill(initial_payload(policy), questions)
    assert outstanding_steps(payload, questions) == []

    payload = compute_and_lock_snapshot(payload, policy)
    snapshot = payload["evaluation_snapshot"]

    assert is_locked(payload)
    assert snapshot["overall_risk_score"] == 1.0
    assert snapshot["risk_category"] == "critical"
    assert snapshot["escalation_required"] is True
    assert "catastrophic_impact" in snapshot["applied_overrides"]
    assert payload["decision"]["decision_type"] == "AVOID"
    assert payload["decision"]["follows_recommendation"] is True


def test_an_override_note_survives_the_round_trip(policy, questions):
    from core.models import DecisionRecord, DecisionType

    record = DecisionRecord(
        decision_type=DecisionType.ACCEPT,
        rationale="Policy recommended AVOID.",
        owner="Hoda",
        follows_recommendation=False,
        override_note="Accepted for a two week pilot with a named review date.",
    )
    dumped = record.model_dump(mode="json")

    assert dumped["override_note"].startswith("Accepted for a two week pilot")
    assert dumped["follows_recommendation"] is False


def test_unknown_fields_are_rejected_rather_than_dropped(policy, questions):
    payload = _fill(initial_payload(policy), questions)
    payload["anchor"]["not_a_field"] = "silently dropped before"

    draft, err = try_make_draft_model(payload)
    assert draft is None
    assert "not_a_field" in str(err)


def test_the_decision_panel_enforces_every_governance_rule(policy):
    from streamlit_app import _decision_problems

    def problems(**kwargs):
        base = dict(
            policy=policy,
            chosen="ACCEPT",
            follows=False,
            category="high",
            role="management",
            decided_by="Hoda",
            approved_by="A second person",
            escalated=True,
            blockers=[],
            note="Accepted for a two week pilot.",
        )
        base.update(kwargs)
        return _decision_problems(**base)

    assert problems() == []
    assert any("documented reason" in p for p in problems(note=""))
    assert any("cannot accept" in p for p in problems(role="risk_owner"))
    assert any("second person" in p for p in problems(approved_by=""))
    assert any("must differ" in p for p in problems(approved_by="Hoda"))
    assert any("Name the person" in p for p in problems(decided_by=""))
    assert any("Acceptance blocked" in p for p in problems(blockers=["Marked not acceptable."]))
    assert problems(chosen="REDUCE", follows=True, note="") == []


def test_questions_cover_only_the_four_input_steps(questions):
    for state in (WizardStateEnum.REVIEW, WizardStateEnum.END):
        assert questions_for_state(questions, state) == []
