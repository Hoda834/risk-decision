from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pydantic import ValidationError

from core.models import (
    AcceptabilityHint,
    AnchorType,
    CauseCategory,
    ImpactDomain,
    LikelihoodBasis,
    Reversibility,
    RiskCaseDraft,
    RiskDirection,
)


class WizardStateEnum(str, Enum):
    ANCHOR = "anchor"
    DEFINITION = "definition"
    LIKELIHOOD = "likelihood"
    IMPACT = "impact"
    REVIEW = "review"
    END = "end"


_STATE_ORDER: List[WizardStateEnum] = [
    WizardStateEnum.ANCHOR,
    WizardStateEnum.DEFINITION,
    WizardStateEnum.LIKELIHOOD,
    WizardStateEnum.IMPACT,
    WizardStateEnum.REVIEW,
    WizardStateEnum.END,
]


@dataclass(frozen=True)
class Question:
    key: str
    label: str
    kind: str  # text | textarea | selectbox | multiselect | slider | textarea_list
    required: bool = True
    help: str = ""
    options: Optional[Sequence[str]] = None
    slider_min: int = 1
    slider_max: int = 5
    slider_step: int = 1


def initial_payload() -> Dict[str, Any]:
    return {
        "case_id": str(uuid.uuid4()),
        "version": 1,
        "wizard": {"state": WizardStateEnum.ANCHOR.value},
        "anchor": {},
        "definition": {},
        "likelihood": {},
        "impact": {},
    }


def set_state(payload: Dict[str, Any], state: WizardStateEnum) -> None:
    payload.setdefault("wizard", {})
    payload["wizard"]["state"] = state.value


def next_state(state: WizardStateEnum) -> WizardStateEnum:
    try:
        idx = _STATE_ORDER.index(state)
    except ValueError:
        return WizardStateEnum.ANCHOR
    return _STATE_ORDER[min(idx + 1, len(_STATE_ORDER) - 1)]


def step_back(payload: Dict[str, Any]) -> WizardStateEnum:
    cur = (payload.get("wizard") or {}).get("state", WizardStateEnum.ANCHOR.value)
    try:
        state = WizardStateEnum(cur)
    except Exception:
        state = WizardStateEnum.ANCHOR

    try:
        idx = _STATE_ORDER.index(state)
    except ValueError:
        return WizardStateEnum.ANCHOR

    return _STATE_ORDER[max(idx - 1, 0)]


def questions_for_state(state: WizardStateEnum) -> List[Question]:
    if state == WizardStateEnum.ANCHOR:
        return [
            Question(
                key="anchor.anchor_type",
                label="What is the anchor type?",
                kind="selectbox",
                options=[e.value for e in AnchorType],
                help="Choose what this risk is anchored to.",
            ),
            Question(key="anchor.name", label="Anchor name", kind="text", help="Short, clear name."),
            Question(
                key="anchor.value_statement",
                label="Why does this matter?",
                kind="textarea",
                help="Explain the value at stake in plain terms.",
            ),
            Question(key="anchor.owner", label="Owner", kind="text", help="Role or team responsible."),
        ]

    if state == WizardStateEnum.DEFINITION:
        return [
            Question(
                key="definition.direction",
                label="Risk direction",
                kind="selectbox",
                options=[e.value for e in RiskDirection],
                help="Downside or upside.",
            ),
            Question(
                key="definition.event",
                label="Risk event",
                kind="textarea",
                help="Describe what could happen.",
            ),
            Question(
                key="definition.vulnerability",
                label="Vulnerability",
                kind="textarea",
                help="Why is this possible in your context?",
            ),
            Question(
                key="definition.triggers",
                label="Triggers (one per line)",
                kind="textarea_list",
                help="Signals you can watch for.",
                required=True,
            ),
            Question(
                key="definition.cause_categories",
                label="Cause categories",
                kind="multiselect",
                options=[e.value for e in CauseCategory],
                help="Select one or more.",
            ),
        ]

    if state == WizardStateEnum.LIKELIHOOD:
        return [
            Question(
                key="likelihood.basis",
                label="Likelihood basis",
                kind="selectbox",
                options=[e.value for e in LikelihoodBasis],
                help="What is your estimate based on?",
            ),
            Question(
                key="likelihood.raw_value",
                label="Likelihood score (1 to 5)",
                kind="slider",
                slider_min=1,
                slider_max=5,
                slider_step=1,
                help="1 = rare, 5 = almost certain.",
            ),
        ]

    if state == WizardStateEnum.IMPACT:
        return [
            Question(
                key="impact.domains",
                label="Impact domains",
                kind="multiselect",
                options=[e.value for e in ImpactDomain],
                help="Select one or more.",
            ),
            Question(
                key="impact.worst_credible_outcome",
                label="Worst credible outcome",
                kind="textarea",
                help="Describe the realistic worst case.",
            ),
            Question(
                key="impact.reversibility",
                label="Reversibility",
                kind="selectbox",
                options=[e.value for e in Reversibility],
                help="How reversible is the impact?",
            ),
            Question(
                key="impact.raw_value",
                label="Impact score (1 to 5)",
                kind="slider",
                slider_min=1,
                slider_max=5,
                slider_step=1,
                help="1 = minor, 5 = severe.",
            ),
            Question(
                key="impact.acceptability_hint",
                label="Is the risk acceptable?",
                kind="selectbox",
                options=[e.value for e in AcceptabilityHint],
                help="A quick acceptability signal.",
            ),
        ]

    return []


def validate_answer_for_question(q: Question, answer: Any) -> Optional[str]:
    if not q.required:
        return None

    if q.kind in {"text", "textarea"}:
        if answer is None or str(answer).strip() == "":
            return "This field is required."

    if q.kind == "textarea_list":
        if answer is None or str(answer).strip() == "":
            return "Add at least one item."
        items = [x.strip() for x in str(answer).splitlines() if x.strip()]
        if not items:
            return "Add at least one item."

    if q.kind == "selectbox":
        if q.options is not None and answer not in q.options:
            return "Choose a valid option."

    if q.kind == "multiselect":
        if not isinstance(answer, list) or len(answer) == 0:
            return "Select at least one option."

    if q.kind == "slider":
        try:
            v = int(answer)
        except Exception:
            return "Enter a number."
        if v < q.slider_min or v > q.slider_max:
            return "Value is out of range."

    return None


def _set_nested(payload: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cur: Any = payload
    for p in parts[:-1]:
        if not isinstance(cur, dict):
            return
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    if isinstance(cur, dict):
        cur[parts[-1]] = value


def apply_answer(payload: Dict[str, Any], key: str, answer: Any) -> Dict[str, Any]:
    if key.endswith(".triggers") and isinstance(answer, str):
        answer = [x.strip() for x in answer.splitlines() if x.strip()]

    _set_nested(payload, key, answer)

    if key == "likelihood.raw_value":
        try:
            rv = int(answer)
            _set_nested(payload, "likelihood.normalised", round(rv / 5.0, 4))
        except Exception:
            pass

    if key == "impact.raw_value":
        try:
            rv = int(answer)
            _set_nested(payload, "impact.normalised", round(rv / 5.0, 4))
        except Exception:
            pass

    return payload


def try_make_draft_model(payload: Dict[str, Any]) -> Tuple[Optional[RiskCaseDraft], Optional[str]]:
    try:
        draft = RiskCaseDraft.model_validate(payload)
        return draft, None
    except ValidationError as e:
        items = []
        for err in e.errors()[:8]:
            loc = ".".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "Invalid value")
            items.append(f"{loc}: {msg}")
        return None, "\n".join(items) if items else "Validation failed."
