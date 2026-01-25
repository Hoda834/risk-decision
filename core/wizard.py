from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from models import (
    AssessmentModel,
    ImpactModel,
    LikelihoodModel,
    RiskCaseDraft,
    RiskModel,
    ThreatVectorModel,
)


class WizardStateEnum(str, Enum):
    DRAFT = "DRAFT"
    ANCHOR = "ANCHOR"
    RISK_EVENT = "RISK_EVENT"
    THREAT_VECTOR = "THREAT_VECTOR"
    CAUSES = "CAUSES"
    ASSESSMENT = "ASSESSMENT"
    IMPACT = "IMPACT"
    SNAPSHOT = "SNAPSHOT"
    DECISION = "DECISION"
    TREATMENT = "TREATMENT"
    ACCEPTANCE = "ACCEPTANCE"
    END = "END"


@dataclass(frozen=True)
class Question:
    key: str
    label: str
    help: str
    kind: str  # text, textarea, selectbox, multiselect, slider
    required: bool = True
    options: Optional[List[str]] = None
    min_len: Optional[int] = None
    max_len: Optional[int] = None
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    slider_min: Optional[float] = None
    slider_max: Optional[float] = None
    slider_step: Optional[float] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def initial_payload() -> Dict[str, Any]:
    now = _now_iso()
    return {
        "case_id": f"case_{int(datetime.now(timezone.utc).timestamp())}",
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "anchor": {
            "name": "",
            "type": "asset",
            "owner": "",
            "value_statement": "",
            "tags": [],
        },
        "risk": {
            "event": "",
            "triggers": [],
            "cause_categories": [],
            "vulnerability": "",
            "threat_vector": {"vector": "human_error", "notes": ""},
            "assumptions": [],
        },
        "assessment": {
            "likelihood": {"raw_value": 1, "normalised": 0.0},
            "impact": {
                "domains": [],
                "worst_credible_outcome": "",
                "reversibility": "reversible",
                "acceptability_hint": "unknown",
                "normalised": 0.0,
            },
            "detectability": {"raw_value": 3, "normalised": 0.0},
            "risk_score": {"raw": 0.0, "weighted": 0.0},
            "notes": "",
        },
        "evaluation_snapshot": None,
        "decision": None,
        "treatment": None,
        "acceptance": None,
        "wizard": {
            "state": WizardStateEnum.ANCHOR.value,
            "history": [],
        },
    }


def questions_for_state(state: WizardStateEnum) -> List[Question]:
    if state == WizardStateEnum.ANCHOR:
        return [
            Question(
                key="anchor.name",
                label="What is the anchor asset or decision object name",
                help="Example: Customer database, Payment gateway, Pricing model",
                kind="text",
                required=True,
                min_len=2,
                max_len=120,
            ),
            Question(
                key="anchor.owner",
                label="Who owns it",
                help="Team or role responsible",
                kind="text",
                required=True,
                min_len=2,
                max_len=120,
            ),
            Question(
                key="anchor.value_statement",
                label="Why does it matter",
                help="One sentence value statement",
                kind="textarea",
                required=True,
                min_len=5,
                max_len=600,
            ),
        ]

    if state == WizardStateEnum.RISK_EVENT:
        return [
            Question(
                key="risk.event",
                label="What could go wrong",
                help="Describe the risk event in plain language",
                kind="textarea",
                required=True,
                min_len=4,
                max_len=800,
            ),
            Question(
                key="risk.triggers",
                label="What would trigger it",
                help="Add at least one trigger",
                kind="multiselect",
                required=True,
                options=[
                    "Process deviation",
                    "Human error",
                    "Supplier failure",
                    "System outage",
                    "Data quality issue",
                    "Security incident",
                    "Regulatory change",
                    "Market change",
                    "Fraud or misuse",
                    "Other",
                ],
                min_items=1,
                max_items=8,
            ),
        ]

    if state == WizardStateEnum.THREAT_VECTOR:
        return [
            Question(
                key="risk.threat_vector.vector",
                label="Threat vector",
                help="Choose the dominant vector",
                kind="selectbox",
                required=True,
                options=["human_error", "malicious", "technical_failure", "process_failure", "external_event"],
            ),
            Question(
                key="risk.threat_vector.notes",
                label="Threat vector notes",
                help="Optional context",
                kind="textarea",
                required=False,
                max_len=500,
            ),
        ]

    if state == WizardStateEnum.CAUSES:
        return [
            Question(
                key="risk.cause_categories",
                label="Cause categories",
                help="Select at least one",
                kind="multiselect",
                required=True,
                options=["people", "process", "technology", "data", "external"],
                min_items=1,
                max_items=5,
            ),
            Question(
                key="risk.vulnerability",
                label="What makes you exposed",
                help="Vulnerability or weakness",
                kind="textarea",
                required=True,
                min_len=4,
                max_len=700,
            ),
        ]

    if state == WizardStateEnum.ASSESSMENT:
        return [
            Question(
                key="assessment.likelihood.raw_value",
                label="Likelihood",
                help="1 low, 2 possible, 3 likely",
                kind="slider",
                required=True,
                slider_min=1,
                slider_max=3,
                slider_step=1,
            ),
            Question(
                key="assessment.detectability.raw_value",
                label="Detectability",
                help="1 hard to detect, 2 medium, 3 easy to detect",
                kind="slider",
                required=True,
                slider_min=1,
                slider_max=3,
                slider_step=1,
            ),
        ]

    if state == WizardStateEnum.IMPACT:
        return [
            Question(
                key="assessment.impact.domains",
                label="Impact domains",
                help="Pick at least one impacted domain",
                kind="multiselect",
                required=True,
                options=["financial", "operations", "legal", "reputation", "customers", "safety"],
                min_items=1,
                max_items=6,
            ),
            Question(
                key="assessment.impact.worst_credible_outcome",
                label="Worst credible outcome",
                help="Describe the worst credible outcome",
                kind="textarea",
                required=True,
                min_len=5,
                max_len=900,
            ),
        ]

    if state == WizardStateEnum.DECISION:
        return [
            Question(
                key="decision",
                label="Decision",
                help="Set the decision recommendation",
                kind="selectbox",
                required=True,
                options=["accept", "mitigate", "avoid", "transfer"],
            )
        ]

    if state == WizardStateEnum.TREATMENT:
        return [
            Question(
                key="treatment",
                label="Treatment plan",
                help="Describe the treatment approach",
                kind="textarea",
                required=False,
                max_len=1200,
            )
        ]

    if state == WizardStateEnum.ACCEPTANCE:
        return [
            Question(
                key="acceptance",
                label="Acceptance note",
                help="Who accepts and why",
                kind="textarea",
                required=False,
                max_len=1200,
            )
        ]

    return []


def validate_answer_for_question(q: Question, answer: Any) -> Optional[str]:
    if q.required:
        if q.kind in {"text", "textarea"}:
            if not isinstance(answer, str) or not answer.strip():
                return "This field is required."
        if q.kind in {"selectbox"}:
            if answer is None or (isinstance(answer, str) and not answer.strip()):
                return "This field is required."
        if q.kind in {"multiselect"}:
            if not isinstance(answer, list) or len(answer) == 0:
                return "Select at least one option."
        if q.kind == "slider":
            if answer is None:
                return "This field is required."

    if isinstance(answer, str):
        if q.min_len is not None and len(answer.strip()) < q.min_len:
            return f"Minimum length is {q.min_len}."
        if q.max_len is not None and len(answer) > q.max_len:
            return f"Maximum length is {q.max_len}."

    if isinstance(answer, list):
        if q.min_items is not None and len(answer) < q.min_items:
            return f"Select at least {q.min_items}."
        if q.max_items is not None and len(answer) > q.max_items:
            return f"Select at most {q.max_items}."

    return None


def _set_nested(payload: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cur: Any = payload
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def apply_answer(payload: Dict[str, Any], question_key: str, answer: Any) -> Dict[str, Any]:
    _set_nested(payload, question_key, answer)
    payload["updated_at"] = _now_iso()
    return payload


def _push_history(payload: Dict[str, Any], state: WizardStateEnum) -> None:
    wiz = payload.setdefault("wizard", {})
    hist = wiz.setdefault("history", [])
    hist.append(state.value)
    if len(hist) > 50:
        del hist[0]


def next_state(current: WizardStateEnum) -> WizardStateEnum:
    order = [
        WizardStateEnum.ANCHOR,
        WizardStateEnum.RISK_EVENT,
        WizardStateEnum.THREAT_VECTOR,
        WizardStateEnum.CAUSES,
        WizardStateEnum.ASSESSMENT,
        WizardStateEnum.IMPACT,
        WizardStateEnum.SNAPSHOT,
        WizardStateEnum.DECISION,
        WizardStateEnum.TREATMENT,
        WizardStateEnum.ACCEPTANCE,
        WizardStateEnum.END,
    ]
    idx = order.index(current) if current in order else 0
    return order[min(idx + 1, len(order) - 1)]


def step_back(payload: Dict[str, Any]) -> WizardStateEnum:
    wiz = payload.get("wizard", {})
    hist: List[str] = wiz.get("history", [])
    if not hist:
        return WizardStateEnum.ANCHOR
    hist.pop()
    prev = hist[-1] if hist else WizardStateEnum.ANCHOR.value
    return WizardStateEnum(prev)


def set_state(payload: Dict[str, Any], state: WizardStateEnum) -> None:
    _push_history(payload, state)
    payload.setdefault("wizard", {})["state"] = state.value
    payload["updated_at"] = _now_iso()


def make_draft_model(payload: Dict[str, Any]) -> RiskCaseDraft:
    return RiskCaseDraft.model_validate(payload)


def try_make_draft_model(payload: Dict[str, Any]) -> Tuple[Optional[RiskCaseDraft], Optional[str]]:
    try:
        return make_draft_model(payload), None
    except ValidationError as e:
        return None, str(e)
