import pytest

from core.policy import load_policy
from core.questions import load_question_bank
from core.wizard import (
    WizardStateEnum,
    apply_answer,
    compute_and_lock_snapshot,
    initial_payload,
    outstanding_steps,
    questions_for_state,
    try_make_draft_model,
)


@pytest.fixture(scope="module")
def policy():
    return load_policy()


@pytest.fixture(scope="module")
def questions(policy):
    return load_question_bank(policy=policy)


def _complete(payload):
    answers = {
        "anchor.name": "Reagent supplier failure",
        "anchor.owner": "Hoda",
        "anchor.value_statement": "Assay availability depends on one supplier.",
        "definition.event": "The sole reagent supplier stops delivering.",
        "definition.triggers": "supplier insolvency\nexport restriction",
        "definition.cause_categories": ["Supplier"],
        "definition.vulnerability": "No qualified second source exists.",
        "definition.consequences": "Production halts for at least one quarter.",
        "definition.time_to_impact_months": 3,
        "definition.scope": "Cartridge manufacturing line.",
        "definition.assumptions": "Current supplier contract stays unchanged.",
        "definition.data_used": "Supplier audit 2026.",
        "definition.references": "QMS-014.",
        "impact.domains": ["Operational"],
        "impact.worst_credible_outcome": "Manufacturing stops for a full quarter.",
        "likelihood.raw_value": 4,
        "impact.raw_value": 4,
    }
    for path, value in answers.items():
        apply_answer(payload, path, value)
    return payload


def test_every_question_maps_to_a_step(questions):
    steps = {q.step for q in questions}
    assert steps == {"anchor", "definition", "likelihood", "impact"}


def test_scale_questions_get_labels_from_policy(questions):
    scale = [q for q in questions if q.input_type == "scale"]
    assert scale
    for q in scale:
        assert sorted(q.option_labels) == [1, 2, 3, 4, 5]


def test_question_options_are_valid_model_values(policy, questions):
    payload = _complete(initial_payload(policy))
    for q in questions:
        if q.options:
            apply_answer(payload, q.path, [q.options[0]] if q.input_type == "multi_select" else q.options[0])
    draft, err = try_make_draft_model(payload)
    assert draft is not None, err


def test_new_case_is_incomplete(policy, questions):
    assert outstanding_steps(initial_payload(policy), questions)


def test_completed_case_has_no_outstanding_steps(policy, questions):
    assert outstanding_steps(_complete(initial_payload(policy)), questions) == []


def test_finish_locks_and_populates_the_snapshot(policy, questions):
    payload = compute_and_lock_snapshot(_complete(initial_payload(policy)), policy)

    assert payload["wizard"]["locked_at_end"] is True
    assert payload["wizard"]["state"] == WizardStateEnum.END.value
    assert payload["evaluation_snapshot"]["overall_risk_score"] == 0.5625
    assert payload["evaluation_snapshot"]["risk_category"] == "high"
    assert payload["decision"]["decision_type"] == "REDUCE"


def test_locked_case_is_not_recomputed(policy):
    payload = compute_and_lock_snapshot(_complete(initial_payload(policy)), policy)
    first = payload["evaluation_snapshot"]["created_at"]

    apply_answer(payload, "likelihood.raw_value", 1)
    payload = compute_and_lock_snapshot(payload, policy)

    assert payload["evaluation_snapshot"]["created_at"] == first


def test_wizard_and_policy_agree_on_normalisation(policy, questions):
    payload = compute_and_lock_snapshot(_complete(initial_payload(policy)), policy)
    assert payload["likelihood"]["normalised"] == policy.normalise_likelihood(4)
    assert payload["impact"]["normalised"] == policy.normalise_impact(4)
