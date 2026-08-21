from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DecisionLevel(str, Enum):
    APPROVE = "approve"
    CONDITIONAL = "conditional"
    REJECT = "reject"


@dataclass(frozen=True)
class DecisionContext:
    decision_id: str
    title: str
    activity: str
    stage: str
    objective: str = ""
    risk_appetite: str = "medium"
    constraints: str = ""
    time_horizon: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainDecision:
    domain: str
    level: DecisionLevel
    score: float
    classification: str
    rationale: List[str] = field(default_factory=list)
    top_contributors: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ActionItem:
    priority: int
    action: str
    deliverables: str = ""
    owner: str = "TBC"
    target_date: str = "TBC"
    related_domain: Optional[str] = None
    related_controls: List[str] = field(default_factory=list)
    evidence_expected: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditFingerprint:
    input_hash: str
    config_hash: str
    model_hash: str = ""


@dataclass(frozen=True)
class DecisionOutput:
    context: DecisionContext
    overall: DecisionLevel
    per_domain: Dict[str, DomainDecision]

    domain_scores: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    category_scores: Dict[str, float] = field(default_factory=dict)

    rationale: List[str] = field(default_factory=list)
    required_actions: List[ActionItem] = field(default_factory=list)

    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    fingerprint: Optional[AuditFingerprint] = None

    warnings: List[str] = field(default_factory=list)
    notes: Dict[str, Any] = field(default_factory=dict)

