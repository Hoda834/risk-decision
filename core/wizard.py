from __future__ import annotations

import hashlib
import json 
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from core.models import (
    AcceptabilityHint,
    AnchorType,
    DecisionRecord,
    DecisionType,
    Direction,
    EvaluationFeedback,
    EvaluationSnapshot,
    ImpactDomain,
    LikelihoodBasis,
    Reversibility,
    RiskCaseDraft,
)


@dataclass(frozen=True)
class QuestionSpec:
    key: str
    label: str
    kind: str
    help: str = ""
    options: Optional[List[str]] = None
    slider_min: int = 1
    slider_max: int = 5
    slider_step: int = 1


class WizardStateEnum(str, Enum):
    ANCHOR = "anchor"
    DEFINITION = "definition"
    LIKELIHOOD = "likelihood"
    IMPACT = "impact"
    REVIEW = "review"
    END = "end"
    DRAFT = "anchor"


_STEPS: List[WizardStateEnum] = [
    WizardStateEnum.ANCHOR,
    WizardStateEnum.DEFINITION,
    WizardStateEnum.LIKELIHOOD,
    WizardStateEnum.IMPACT,
    WizardStateEnum.REVIEW,
    WizardStateEnum.END,
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_state(payload: Dict[str, Any]) -> WizardStateEnum:
    state_str = (payload.get("wizard") or {}).get("state", WizardStateEnum.ANCHOR.value)
    try:
        return WizardStateEnum(state_str)
    except Exception:
        return WizardStateEnum.ANCHOR


def set_state(payload: Dict[str, Any], state: WizardStateEnum) -> None:
    wiz = payload.get("wizard")
    if not isinstance(wiz, dict):
        wiz = {}
        payload["wizard"] = wiz
    wiz["state"] = state.value


def next_state(state: WizardStateEnum) -> WizardStateEnum:
    try:
        idx = _STEPS.index(state)
    except ValueError:
        return WizardStateEnum.ANCHOR
    return _STEPS[min(idx + 1, len(_STEPS) - 1)]


def prev_state(state: WizardStateEnum) -> WizardStateEnum:
    try:
        idx = _STEPS.index(state)
    except ValueError:
        return WizardStateEnum.ANCHOR
    return _STEPS[max(idx - 1, 0)]


def _enum_options(enum_cls) -> List[str]:
    return [e.value for e in enum_cls]


def questions_for_state(state: WizardStateEnum) -> List[QuestionSpec]:
    if state == WizardStateEnum.ANCHOR:
        return [
            QuestionSpec("anchor.name", "Case name", "text"),
            QuestionSpec("anchor.owner", "Owner", "text"),
            QuestionSpec("anchor.anchor_type", "Anchor type", "selectbox", options=_enum_options(AnchorType)),
            QuestionSpec("anchor.value_statement", "Value statement", "textarea"),
            QuestionSpec("anchor.direction", "Direction", "selectbox", options=_enum_options(Direction)),
        ]

    if state == WizardStateEnum.DEFINITION:
        return [
            QuestionSpec("definition.event", "Event", "textarea"),
            QuestionSpec("definition.triggers", "Triggers", "textarea", help="One per line"),
            QuestionSpec(
                "definition.cause_categories",
                "Cause categories",
                "multiselect",
                options=["People", "Process", "Technology", "Data", "Supplier", "Finance", "Regulatory", "Market", "Other"],
            ),
            QuestionSpec("definition.vulnerability", "Vulnerability", "textarea"),
            QuestionSpec("definition.consequences", "Consequences", "textarea"),
            QuestionSpec("definition.time_to_impact_months", "Time to impact (months)", "number"),
            QuestionSpec("definition.scope", "Scope", "textarea"),
            QuestionSpec("definition.assumptions", "Assumptions", "textarea"),
            QuestionSpec("definition.data_used", "Data used", "textarea"),
            QuestionSpec("definition.references", "References", "textarea"),
        ]

    if state == WizardStateEnum.LIKELIHOOD:
        return [
            QuestionSpec("likelihood.basis", "Likelihood basis", "selectbox", options=_enum_options(LikelihoodBasis)),
            QuestionSpec("likelihood.signals", "Signals", "textarea", help="One per line"),
            QuestionSpec("likelihood.raw_value", "Likelihood (1-5)", "slider", slider_min=1, slider_max=5),
            QuestionSpec("likelihood.confidence", "Confidence (1-5)", "slider", slider_min=1, slider_max=5),
        ]

    if state == WizardStateEnum.IMPACT:
        return [
            QuestionSpec("impact.domains", "Impact domains", "multiselect", options=_enum_options(ImpactDomain)),
            QuestionSpec("impact.worst_credible_outcome", "Worst credible outcome", "textarea"),
            QuestionSpec("impact.reversibility", "Reversibility", "selectbox", options=_enum_options(Reversibility)),
            QuestionSpec("impact.raw_value", "Impact severity (1-5)", "slider", slider_min=1, slider_max=5),
            QuestionSpec("impact.confidence", "Confidence (1-5)", "slider", slider_min=1, slider_max=5),
            QuestionSpec(
                "impact.acceptability_hint",
                "Acceptability hint",
                "selectbox",
                options=_enum_options(AcceptabilityHint),
            ),
        ]

    return []


def _get_nested(payload: Dict[str, Any], key: str) -> Any:
    cur: Any = payload
    for part in key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _set_nested(payload: Dict[str, Any], key: str, value: Any) -> None:
    parts = key.split(".")
    cur: Any = payload
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def apply_answer(payload: Dict[str, Any], key: str, answer: Any) -> Dict[str, Any]:
    if key in {"definition.triggers", "likelihood.signals"}:
        if isinstance(answer, str):
            items = [x.strip() for x in answer.splitlines() if x.strip()]
            _set_nested(payload, key, items)
            return payload

    if key == "definition.cause_categories":
        if isinstance(answer, list):
            _set_nested(payload, key, list(dict.fromkeys(answer)))
            return payload

    _set_nested(payload, key, answer)
    return payload


def validate_answer_for_question(q: QuestionSpec, answer: Any) -> Optional[str]:
    if q.kind in {"text", "textarea"}:
        if answer is None:
            return "Required."
        if isinstance(answer, str) and not answer.strip():
            return "Required."
        return None

    if q.kind == "multiselect":
        if not isinstance(answer, list) or len(answer) == 0:
            return "Select at least one item."
        return None

    if q.kind == "number":
        if answer is None:
            return "Required."
        try:
            v = int(answer)
        except Exception:
            return "Enter a number."
        if v < 0:
            return "Must be 0 or above."
        return None

    if q.kind in {"selectbox", "slider"}:
        if answer is None:
            return "Required."
        return None

    return None


def initial_payload() -> Dict[str, Any]:
    return {
        "case_id": hashlib.sha1(_now_iso().encode("utf-8")).hexdigest()[:12],
        "version": 1,
        "wizard": {"state": WizardStateEnum.ANCHOR.value, "locked_at_end": False},
        "anchor": {
            "anchor_type": AnchorType.PROBLEM.value,
            "value_statement": "",
            "direction": Direction.NEGATIVE.value,
            "name": "Untitled case",
            "owner": "",
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
            "raw_value": 1,
            "normalised": 0.2,
            "confidence": 3,
        },
        "impact": {
            "domains": [],
            "worst_credible_outcome": "",
            "reversibility": Reversibility.PARTIALLY_REVERSIBLE.value,
            "raw_value": 1,
            "normalised": 0.2,
            "confidence": 3,
            "acceptability_hint": AcceptabilityHint.TOLERABLE.value,
        },
        "evaluation_snapshot": None,
        "decision": None,
        "feedback": None,
    }


def make_draft_model(payload: Dict[str, Any]) -> RiskCaseDraft:
    return RiskCaseDraft.model_validate(payload)


def try_make_draft_model(payload: Dict[str, Any]) -> Tuple[Optional[RiskCaseDraft], Optional[str]]:
    try:
        draft = make_draft_model(payload)
        return draft, None
    except ValidationError as e:
        return None, e.json()
    except Exception as e:
        return None, str(e)


def _normalise_1_to_5(raw: int) -> float:
    raw = max(1, min(5, int(raw)))
    return raw / 5.0


def compute_and_lock_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    from pathlib import Path
    from core.engine import compute_snapshot, acceptance_requires_escalation
    from core.policy import load_policy

    wiz = payload.get("wizard")
    if not isinstance(wiz, dict):
        wiz = {}
        payload["wizard"] = wiz

    if wiz.get("locked_at_end") is True:
        return payload

    policy_path = Path(__file__).parent.parent / "config" / "policy_config.json"
    policy = load_policy(policy_path)

    draft_payload = {
        "likelihood": {
            "raw_value": int(_get_nested(payload, "likelihood.raw_value") or 1),
            "basis": _get_nested(payload, "likelihood.basis"),
        },
        "impact": {
            "raw_value": int(_get_nested(payload, "impact.raw_value") or 1),
            "domains": _get_nested(payload, "impact.domains"),
            "reversibility": _get_nested(payload, "impact.reversibility"),
            "acceptability_hint": _get_nested(payload, "impact.acceptability_hint"),
            "worst_credible_outcome": _get_nested(payload, "impact.worst_credible_outcome"),
        },
        "anchor": payload.get("anchor"),
        "definition": payload.get("definition"),
    }

    snap = compute_snapshot(draft_payload, policy)
    requires_escalation = acceptance_requires_escalation(snap, policy)

    rec = policy.recommend_decision(snap.overall_risk_score)
    _decision_map = {
        "accept": DecisionType.ACCEPT,
        "reduce": DecisionType.REDUCE,
        "avoid": DecisionType.AVOID,
        "defer": DecisionType.DEFER,
        "transfer": DecisionType.TRANSFER,
    }
    decision_type = _decision_map.get(rec, DecisionType.REDUCE)

    # Check privacy or catastrophic signals in the payload
    definition_text = json.dumps(payload.get("definition", {}), ensure_ascii=False).lower()
    privacy_hit = any(kw in definition_text for kw in policy.privacy_keywords())
    impact_raw = int(_get_nested(payload, "impact.raw_value") or 1)
    catastrophic_hit = impact_raw >= policy.catastrophic_if_impact_level_gte()

    _set_nested(payload, "likelihood.normalised", policy.normalise_likelihood(int(_get_nested(payload, "likelihood.raw_value") or 1)))
    _set_nested(payload, "impact.normalised", policy.normalise_impact(int(_get_nested(payload, "impact.raw_value") or 1)))

    rationale_parts = [f"Score {snap.overall_risk_score} maps to category '{snap.risk_category}' under policy {snap.policy_version}."]
    if requires_escalation:
        rationale_parts.append("Score meets or exceeds acceptance threshold — escalation required.")
    if privacy_hit:
        rationale_parts.append("Privacy-sensitive signals detected in definition.")
    if catastrophic_hit:
        rationale_parts.append("Impact severity meets catastrophic threshold.")

    decision = DecisionRecord(
        decision_type=decision_type.value,
        rationale=" ".join(rationale_parts),
        owner=str(_get_nested(payload, "anchor.owner") or "TBC"),
    )

    feedback_messages = [f"Risk category: {snap.risk_category}."]
    if requires_escalation or privacy_hit or catastrophic_hit:
        feedback_messages.append("Escalation required — refer to authority matrix for approval.")
    else:
        feedback_messages.append("No escalation required under current policy.")

    payload["evaluation_snapshot"] = snap.model_dump()
    payload["decision"] = decision.model_dump()
    payload["feedback"] = EvaluationFeedback(messages=feedback_messages).model_dump()
    wiz["locked_at_end"] = True
    set_state(payload, WizardStateEnum.END)
    return payload
