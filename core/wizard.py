from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import uuid

from core.engine import compute_snapshot
from core.models import (
    DecisionRecord,
    EvaluationFeedback,
    RiskCaseDraft,
    RiskAnchor,
    RiskDefinition,
    LikelihoodAssessment,
    ImpactAssessment,
)
from core.policy import PolicyConfig
from core.questions import Question
from core.utils import get_nested, set_nested


@dataclass
class WizardState:
    case_id: str
    version: int
    policy_version: str
    current_index: int
    snapshot_locked: bool


def new_case_id() -> str:
    return uuid.uuid4().hex[:12]


def initial_payload(policy: PolicyConfig, case_id: str, version: int) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    return {
        "case_id": case_id,
        "version": version,
        "policy_version": policy.policy_version,
        "created_at": now,
        "updated_at": now,
        "anchor": {"anchor_type": "asset", "name": "", "value_statement": "", "owner": ""},
        "definition": {
            "direction": "downside",
            "event": "",
            "triggers": [],
            "cause_categories": [],
            "vulnerability": "",
            "assumptions": [],
        },
        "likelihood": {"basis": "expert_judgement", "raw_value": 1, "normalised": 0.0},
        "impact": {
            "domains": [],
            "worst_credible_outcome": "",
            "reversibility": "fully",
            "raw_value": 1,
            "normalised": 0.0,
            "acceptability_hint": "no",
        },
        "evaluation_snapshot": None,
        "evaluation_feedback": None,
        "decision": None,
    }


def can_go_back(state: WizardState) -> bool:
    if state.snapshot_locked:
        return False
    return state.current_index > 0


def apply_answer(payload: Dict[str, Any], question: Question, value: Any, policy: PolicyConfig) -> None:
    set_nested(payload, question.path, value)
    payload["updated_at"] = datetime.utcnow().isoformat()

    if question.path == "likelihood.raw_value":
        raw = int(get_nested(payload, "likelihood.raw_value"))
        payload["likelihood"]["normalised"] = policy.normalise_likelihood(raw)

    if question.path == "impact.raw_value":
        raw = int(get_nested(payload, "impact.raw_value"))
        payload["impact"]["normalised"] = policy.normalise_impact(raw)


def required_if_met(payload: Dict[str, Any], question: Question) -> bool:
    if question.required_if is None:
        return question.required
    cond_path = str(question.required_if["path"])
    equals = question.required_if.get("equals")
    current = get_nested(payload, cond_path)
    return str(current).lower() == str(equals).lower()


def should_compute_snapshot(question_id: str) -> bool:
    return question_id == "Q17"


def compute_and_lock_snapshot(payload: Dict[str, Any], policy: PolicyConfig) -> None:
    snap = compute_snapshot(payload, policy)
    payload["evaluation_snapshot"] = snap.model_dump()
    payload["evaluation_feedback"] = None
    payload["decision"] = None


def make_draft_model(payload: Dict[str, Any]) -> RiskCaseDraft:
    return RiskCaseDraft.model_validate(payload)


def clone_to_new_version(payload: Dict[str, Any], policy: PolicyConfig) -> Tuple[Dict[str, Any], int]:
    current_version = int(payload["version"])
    new_version = current_version + 1
    new_payload = dict(payload)
    new_payload["version"] = new_version
    new_payload["policy_version"] = policy.policy_version
    new_payload["updated_at"] = datetime.utcnow().isoformat()
    new_payload["evaluation_snapshot"] = None
    new_payload["evaluation_feedback"] = None
    new_payload["decision"] = None
    return new_payload, new_version
