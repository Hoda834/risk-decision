from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.models import (
    AcceptabilityHint,
    AnchorType,
    Direction,
    ImpactDomain,
    LikelihoodBasis,
    Reversibility,
)
from core.policy import PolicyConfig, load_policy

DEFAULT_QUESTION_BANK_PATH = Path(__file__).resolve().parents[1] / "config" / "question_bank.json"

STEPS = ("anchor", "definition", "likelihood", "impact")

INPUT_TYPES = {
    "text",
    "textarea",
    "list_text",
    "single_select",
    "multi_select",
    "number",
    "slider",
    "scale",
}

# Options declared in the question bank resolve against these at load time, so a
# question pointing at a value the model no longer accepts fails on load rather
# than at validation.
ENUM_REGISTRY = {
    "AnchorType": AnchorType,
    "Direction": Direction,
    "LikelihoodBasis": LikelihoodBasis,
    "ImpactDomain": ImpactDomain,
    "Reversibility": Reversibility,
    "AcceptabilityHint": AcceptabilityHint,
}

POLICY_LABEL_SOURCES = {
    "scales.likelihood.labels": "likelihood",
    "scales.impact.labels": "impact",
}

VAGUE_PHRASES = {
    "risk",
    "issue",
    "problem",
    "failure",
    "something bad happens",
    "it goes wrong",
    "tbc",
    "tbd",
    "n/a",
}

MIN_WORDS_WHEN_REJECTING_VAGUE = 3


@dataclass(frozen=True)
class Question:
    qid: str
    step: str
    text: str
    input_type: str
    required: bool
    path: str
    help: str = ""
    options: Optional[List[Any]] = None
    option_labels: Optional[Dict[int, str]] = None
    validation: Dict[str, Any] = field(default_factory=dict)
    required_if: Optional[Dict[str, Any]] = None
    checkpoint: Optional[str] = None


def load_question_bank(
    path: Optional[Path] = None,
    policy: Optional[PolicyConfig] = None,
) -> List[Question]:
    p = Path(path) if path is not None else DEFAULT_QUESTION_BANK_PATH
    pol = policy if policy is not None else load_policy()

    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Question bank must be a list")

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    out: List[Question] = []

    for item in raw:
        qid = str(item["id"])
        if qid in seen_ids:
            raise ValueError(f"Duplicate question id: {qid}")
        seen_ids.add(qid)

        step = str(item["step"])
        if step not in STEPS:
            raise ValueError(f"{qid} declares an unknown step: {step}")

        input_type = str(item["input_type"])
        if input_type not in INPUT_TYPES:
            raise ValueError(f"{qid} declares an unknown input type: {input_type}")

        qpath = str(item["path"])
        if qpath in seen_paths:
            raise ValueError(f"Two questions write to the same path: {qpath}")
        seen_paths.add(qpath)
        if not qpath.startswith(f"{step}."):
            raise ValueError(f"{qid} is in step {step} but writes to {qpath}")

        options, option_labels = _resolve_options(qid, item, pol)

        out.append(
            Question(
                qid=qid,
                step=step,
                text=str(item["text"]),
                input_type=input_type,
                required=bool(item.get("required", False)),
                path=qpath,
                help=str(item.get("help", "")),
                options=options,
                option_labels=option_labels,
                validation=dict(item.get("validation") or {}),
                required_if=dict(item["required_if"]) if item.get("required_if") else None,
                checkpoint=str(item["checkpoint"]) if item.get("checkpoint") else None,
            )
        )

    _check_every_step_is_covered(out)
    return out


def _resolve_options(
    qid: str,
    item: Dict[str, Any],
    policy: PolicyConfig,
) -> tuple[Optional[List[Any]], Optional[Dict[int, str]]]:
    sources = [k for k in ("options", "options_from_enum", "options_from_policy") if item.get(k)]
    if len(sources) > 1:
        raise ValueError(f"{qid} declares more than one option source: {sources}")

    if item.get("options_from_enum"):
        name = str(item["options_from_enum"])
        enum_cls = ENUM_REGISTRY.get(name)
        if enum_cls is None:
            raise ValueError(f"{qid} references an unknown enum: {name}")
        return [e.value for e in enum_cls], None

    if item.get("options_from_policy"):
        source = str(item["options_from_policy"])
        dimension = POLICY_LABEL_SOURCES.get(source)
        if dimension is None:
            raise ValueError(f"{qid} references an unknown policy option source: {source}")
        labels = policy.likelihood_labels() if dimension == "likelihood" else policy.impact_labels()
        vmin, vmax = policy.scale_bounds(dimension)
        points = list(range(vmin, vmax + 1))
        if sorted(labels) != points:
            raise ValueError(f"{qid} scale labels do not cover {vmin} to {vmax}")
        return points, labels

    if item.get("options"):
        return list(item["options"]), None

    if item["input_type"] in {"single_select", "multi_select", "scale"}:
        raise ValueError(f"{qid} is a {item['input_type']} question with no options")

    return None, None


def _check_every_step_is_covered(questions: List[Question]) -> None:
    covered = {q.step for q in questions}
    missing = [s for s in STEPS if s not in covered]
    if missing:
        raise ValueError(f"Question bank has no questions for steps: {missing}")


def questions_for_step(questions: List[Question], step: str) -> List[Question]:
    return [q for q in questions if q.step == step]


def is_vague(text: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9 ]", " ", text.strip().lower())
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return True
    if cleaned in VAGUE_PHRASES:
        return True
    return len(cleaned.split()) < MIN_WORDS_WHEN_REJECTING_VAGUE
