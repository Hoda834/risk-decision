from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from core.engine import compute_snapshot
from core.models import (
    AcceptabilityHint,
    AnchorType,
    DecisionRecord,
    Direction,
    EvaluationFeedback,
    LikelihoodBasis,
    Reversibility,
    RiskCaseDraft,
)
from core.policy import PolicyConfig
from core.questions import Question, is_vague, questions_for_step
from core.utils import get_nested, set_nested

# Paths that hold a list. Everything else is stored as given.
LIST_PATHS = {
    "definition.triggers",
    "definition.cause_categories",
    "likelihood.signals",
    "impact.domains",
}


class WizardStateEnum(str, Enum):
    ANCHOR = "anchor"
    DEFINITION = "definition"
    LIKELIHOOD = "likelihood"
    IMPACT = "impact"
    REVIEW = "review"
    END = "end"


_STEPS: List[WizardStateEnum] = list(WizardStateEnum)

# Steps that collect answers. Review and end do not.
QUESTION_STEPS: List[WizardStateEnum] = [
    WizardStateEnum.ANCHOR,
    WizardStateEnum.DEFINITION,
    WizardStateEnum.LIKELIHOOD,
    WizardStateEnum.IMPACT,
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_state(payload: Dict[str, Any]) -> WizardStateEnum:
    state_str = (payload.get("wizard") or {}).get("state", WizardStateEnum.ANCHOR.value)
    try:
        return WizardStateEnum(state_str)
    except ValueError:
        return WizardStateEnum.ANCHOR


def set_state(payload: Dict[str, Any], state: WizardStateEnum) -> None:
    wiz = payload.get("wizard")
    if not isinstance(wiz, dict):
        wiz = {}
        payload["wizard"] = wiz
    wiz["state"] = state.value


def is_locked(payload: Dict[str, Any]) -> bool:
    return bool((payload.get("wizard") or {}).get("locked_at_end", False))


def next_state(state: WizardStateEnum) -> WizardStateEnum:
    idx = _STEPS.index(state)
    return _STEPS[min(idx + 1, len(_STEPS) - 1)]


def prev_state(state: WizardStateEnum) -> WizardStateEnum:
    idx = _STEPS.index(state)
    return _STEPS[max(idx - 1, 0)]


def questions_for_state(questions: List[Question], state: WizardStateEnum) -> List[Question]:
    return questions_for_step(questions, state.value)


def initial_payload(policy: PolicyConfig) -> Dict[str, Any]:
    likelihood_min, _ = policy.scale_bounds("likelihood")
    impact_min, _ = policy.scale_bounds("impact")

    return {
        "case_id": _new_case_id(),
        "version": 1,
        "wizard": {"state": WizardStateEnum.ANCHOR.value, "locked_at_end": False},
        "anchor": {
            "anchor_type": AnchorType.PROBLEM.value,
            "name": "",
            "value_statement": "",
            "owner": "",
            "direction": Direction.NEGATIVE.value,
        },
        "definition": {
            "event": "",
            "triggers": [],
            "cause_categories": [],
            "vulnerability": "",
            "consequences": "",
            "time_to_impact_months": 0,
            "scope": "",
            "assumptions": "",
            "data_used": "",
            "references": "",
        },
        "likelihood": {
            "basis": LikelihoodBasis.EXPERT_JUDGEMENT.value,
            "signals": [],
            "raw_value": likelihood_min,
            "normalised": policy.normalise_likelihood(likelihood_min),
            "confidence": 3,
        },
        "impact": {
            "domains": [],
            "worst_credible_outcome": "",
            "reversibility": Reversibility.PARTIALLY_REVERSIBLE.value,
            "raw_value": impact_min,
            "normalised": policy.normalise_impact(impact_min),
            "confidence": 3,
            "acceptability_hint": AcceptabilityHint.TOLERABLE.value,
        },
        "evaluation_snapshot": None,
        "decision": None,
        "feedback": None,
    }


def _new_case_id() -> str:
    seed = f"{_now_iso()}-{uuid.uuid4()}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def apply_answer(payload: Dict[str, Any], path: str, answer: Any) -> Dict[str, Any]:
    if path in LIST_PATHS:
        set_nested(payload, path, _as_list(answer))
        return payload

    if isinstance(answer, str):
        set_nested(payload, path, answer.strip())
        return payload

    set_nested(payload, path, answer)
    return payload


def _as_list(answer: Any) -> List[str]:
    if isinstance(answer, str):
        items = [line.strip() for line in answer.splitlines() if line.strip()]
    elif isinstance(answer, (list, tuple)):
        items = [str(x).strip() for x in answer if str(x).strip()]
    elif answer in (None, ""):
        items = []
    else:
        items = [str(answer).strip()]
    return list(dict.fromkeys(items))


def validate_answer(q: Question, answer: Any) -> Optional[str]:
    rules = q.validation or {}
    empty = answer is None or (isinstance(answer, str) and not answer.strip()) or answer == []

    if empty:
        return "Required." if q.required else None

    if q.input_type in {"text", "textarea"}:
        text = str(answer).strip()
        if "min_length" in rules and len(text) < int(rules["min_length"]):
            return f"Use at least {rules['min_length']} characters."
        if "max_length" in rules and len(text) > int(rules["max_length"]):
            return f"Use at most {rules['max_length']} characters."
        if rules.get("reject_vague") and is_vague(text):
            return "Too vague. Describe a specific event."
        return None

    if q.input_type == "list_text":
        items = _as_list(answer)
        if q.required and len(items) < int(rules.get("min_items", 1)):
            return f"Give at least {rules.get('min_items', 1)} item(s), one per line."
        min_item_length = int(rules.get("min_item_length", 0))
        if any(len(i) < min_item_length for i in items):
            return f"Each item needs at least {min_item_length} characters."
        return None

    if q.input_type == "multi_select":
        items = _as_list(answer)
        if len(items) < int(rules.get("min_items", 1)):
            return "Select at least one item."
        unknown = [i for i in items if q.options and i not in q.options]
        if unknown:
            return f"Not a valid option: {', '.join(unknown)}"
        return None

    if q.input_type == "single_select":
        if q.options and answer not in q.options:
            return f"Not a valid option: {answer}"
        return None

    if q.input_type in {"number", "slider", "scale"}:
        try:
            value = int(answer)
        except (TypeError, ValueError):
            return "Enter a whole number."
        if q.input_type == "scale" and q.options and value not in q.options:
            return f"Choose a point between {min(q.options)} and {max(q.options)}."
        if "min" in rules and value < int(rules["min"]):
            return f"Must be {rules['min']} or above."
        if "max" in rules and value > int(rules["max"]):
            return f"Must be {rules['max']} or below."
        return None

    return None


def step_errors(
    payload: Dict[str, Any],
    questions: List[Question],
    state: WizardStateEnum,
) -> Dict[str, str]:
    errors: Dict[str, str] = {}
    for q in questions_for_state(questions, state):
        message = validate_answer(q, get_nested(payload, q.path))
        if message:
            errors[q.path] = message
    return errors


def outstanding_steps(payload: Dict[str, Any], questions: List[Question]) -> List[str]:
    return [s.value for s in QUESTION_STEPS if step_errors(payload, questions, s)]


def suggested_review_date(payload: Dict[str, Any], today: Optional[date] = None) -> date:
    """Half the time to impact, capped at a year, floored at a month.

    Time to impact is collected anyway. Using it for the review interval is more
    honest than asking for a date with no anchor.
    """
    base = today or datetime.now(timezone.utc).date()
    months = int(get_nested(payload, "definition.time_to_impact_months") or 0)
    interval = min(12, max(1, months // 2 if months else 3))
    return base + timedelta(days=interval * 30)


def make_draft_model(payload: Dict[str, Any]) -> RiskCaseDraft:
    return RiskCaseDraft.model_validate(payload)


def try_make_draft_model(payload: Dict[str, Any]) -> Tuple[Optional[RiskCaseDraft], Optional[str]]:
    try:
        return make_draft_model(payload), None
    except ValidationError as e:
        return None, e.json()
    except Exception as e:  # pragma: no cover - defensive
        return None, str(e)


def compute_and_lock_snapshot(payload: Dict[str, Any], policy: PolicyConfig) -> Dict[str, Any]:
    """Evaluate under the policy and lock the version.

    A locked version is never recomputed. Revising means a new version.
    """
    wiz = payload.get("wizard")
    if not isinstance(wiz, dict):
        wiz = {"state": WizardStateEnum.ANCHOR.value, "locked_at_end": False}
        payload["wizard"] = wiz

    if wiz.get("locked_at_end") is True:
        return payload

    snapshot = compute_snapshot(payload, policy)

    set_nested(payload, "likelihood.normalised", snapshot.likelihood_normalised)
    set_nested(payload, "impact.normalised", snapshot.impact_normalised)

    likelihood_raw = int(get_nested(payload, "likelihood.raw_value"))
    impact_raw = int(get_nested(payload, "impact.raw_value"))

    decision = DecisionRecord(
        decision_type=snapshot.recommended_decision,
        rationale=(
            f"Policy {snapshot.policy_version} placed likelihood {likelihood_raw} against impact "
            f"{impact_raw} in the {snapshot.matrix_category} cell, classified {snapshot.risk_category}."
        ),
        owner=str(get_nested(payload, "anchor.owner") or "unassigned"),
        follows_recommendation=True,
        override_note="",
    )

    messages = [
        f"Category read from the {snapshot.matrix_category} matrix cell under policy "
        f"{snapshot.policy_version}. The score of {snapshot.overall_risk_score} orders cases, "
        "it does not classify them.",
        f"Inputs hash {snapshot.inputs_hash[:12]} covers the assessed inputs only.",
    ]
    for name in snapshot.applied_overrides:
        reason = policy.overrides().get(name, {}).get("reason", "")
        messages.append(f"Override applied: {name}. {reason}".strip())
    messages.extend(f"Escalation: {reason}" for reason in snapshot.escalation_reasons)
    messages.extend(f"Acceptance blocked: {reason}" for reason in snapshot.accept_blockers)
    if snapshot.roles_that_may_accept:
        messages.append(
            "Roles that may accept this category: " + ", ".join(snapshot.roles_that_may_accept) + "."
        )

    payload["evaluation_snapshot"] = snapshot.model_dump(mode="json")
    payload["decision"] = decision.model_dump(mode="json")
    payload["feedback"] = EvaluationFeedback(messages=messages).model_dump(mode="json")

    wiz["locked_at_end"] = True
    set_state(payload, WizardStateEnum.END)
    return payload
