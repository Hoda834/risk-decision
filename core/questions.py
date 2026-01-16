from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.policy import PolicyConfig


@dataclass(frozen=True)
class Question:
    qid: str
    text: str
    input_type: str
    required: bool
    path: str
    options: Optional[List[str]] = None
    options_from_policy: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None
    required_if: Optional[Dict[str, Any]] = None
    checkpoint: Optional[str] = None


def load_question_bank(path: Path) -> List[Question]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Question bank must be a list")
    out: List[Question] = []
    for item in raw:
        out.append(
            Question(
                qid=str(item["id"]),
                text=str(item["text"]),
                input_type=str(item["input_type"]),
                required=bool(item.get("required", False)),
                path=str(item["path"]),
                options=list(item.get("options")) if item.get("options") is not None else None,
                options_from_policy=str(item.get("options_from_policy")) if item.get("options_from_policy") is not None else None,
                validation=dict(item.get("validation")) if item.get("validation") is not None else None,
                required_if=dict(item.get("required_if")) if item.get("required_if") is not None else None,
                checkpoint=str(item.get("checkpoint")) if item.get("checkpoint") is not None else None,
            )
        )
    return out


def resolve_options(question: Question, policy: PolicyConfig) -> Optional[List[str]]:
    if question.options is not None:
        return question.options
    if question.options_from_policy is None:
        return None
    if question.options_from_policy == "scales.likelihood.labels":
        return list(policy.likelihood_labels().keys())
    if question.options_from_policy == "scales.impact.labels":
        return list(policy.impact_labels().keys())
    return None


def option_labels(question: Question, policy: PolicyConfig) -> Optional[Dict[str, str]]:
    if question.options_from_policy == "scales.likelihood.labels":
        return policy.likelihood_labels()
    if question.options_from_policy == "scales.impact.labels":
        return policy.impact_labels()
    return None
