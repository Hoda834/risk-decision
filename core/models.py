from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import re
from pydantic import BaseModel, Field, field_validator, model_validator


class AnchorType(str, Enum):
    ASSET = "asset"
    OBJECTIVE = "objective"
    PROCESS = "process"
    OBLIGATION = "obligation"
    OPPORTUNITY = "opportunity"


class RiskDirection(str, Enum):
    DOWNSIDE = "downside"
    UPSIDE = "upside"


class CauseCategory(str, Enum):
    HUMAN = "human"
    TECHNICAL = "technical"
    ORGANISATIONAL = "organisational"
    EXTERNAL = "external"
    UNKNOWN_ASSUMPTION = "unknown_or_assumption"


class ImpactDomain(str, Enum):
    FINANCIAL = "financial"
    LEGAL_COMPLIANCE = "legal_or_compliance"
    OPERATIONAL = "operational"
    SAFETY = "safety"
    REPUTATION = "reputation"
    STRATEGIC = "strategic"


class Reversibility(str, Enum):
    FULLY = "fully"
    PARTIALLY = "partially"
    NOT_REVERSIBLE = "not_reversible"


class LikelihoodBasis(str, Enum):
    HISTORICAL_DATA = "historical_data"
    MEASURED_DATA = "measured_data"
    EXPERT_JUDGEMENT = "expert_judgement"
    ASSUMPTION = "assumption"


class AcceptabilityHint(str, Enum):
    YES = "yes"
    NO = "no"
    ONLY_UNDER_CONDITIONS = "only_under_conditions"


class DecisionType(str, Enum):
    ACCEPT = "accept"
    REDUCE = "reduce"
    TRANSFER = "transfer"
    AVOID = "avoid"
    DEFER = "defer"


class RiskAnchor(BaseModel):
    anchor_type: AnchorType
    name: str = Field(..., min_length=2, max_length=120)
    value_statement: str = Field(..., min_length=10, max_length=800)
    owner: str = Field(..., min_length=2, max_length=120)


class RiskDefinition(BaseModel):
    direction: RiskDirection
    event: str = Field(..., min_length=10, max_length=500)
    triggers: List[str] = Field(..., min_length=1)
    cause_categories: Set[CauseCategory] = Field(..., min_length=1)
    vulnerability: str = Field(..., min_length=10, max_length=800)
    assumptions: List[str] = Field(default_factory=list)

    @field_validator("triggers")
    @classmethod
    def validate_triggers(cls, v: List[str]) -> List[str]:
        cleaned = [t.strip() for t in v if t and t.strip()]
        if len(cleaned) < 1:
            raise ValueError("At least one trigger is required.")
        if any(len(t) < 3 for t in cleaned):
            raise ValueError("Each trigger must be at least 3 characters long.")
        return cleaned

    @field_validator("event")
    @classmethod
    def validate_event_specificity(cls, v: str) -> str:
        text = v.strip()
        banned_patterns = [
            r"\bsomething (bad|wrong)\b",
            r"\bissues?\b",
            r"\bproblem(s)?\b",
            r"\brisk happens\b",
        ]
        if any(re.search(p, text, flags=re.IGNORECASE) for p in banned_patterns):
            raise ValueError("Event description is too vague.")
        if len(text.split()) < 5:
            raise ValueError("Event description is too short.")
        return text


class LikelihoodAssessment(BaseModel):
    basis: LikelihoodBasis
    raw_value: int = Field(..., ge=1, le=3)
    normalised: float = Field(..., ge=0, le=1)


class ImpactAssessment(BaseModel):
    domains: Set[ImpactDomain] = Field(..., min_length=1)
    worst_credible_outcome: str = Field(..., min_length=10, max_length=900)
    reversibility: Reversibility
    raw_value: int = Field(..., ge=1, le=3)
    normalised: float = Field(..., ge=0, le=1)
    acceptability_hint: AcceptabilityHint


class EvaluationSnapshot(BaseModel):
    policy_version: str
    created_at: datetime
    likelihood_normalised: float
    impact_normalised: float
    score: float
    category: str
    recommended_decision: str
    inputs_hash: str


class EvaluationFeedback(BaseModel):
    confirmed: bool
    challenge_note: Optional[str] = Field(default=None, max_length=700)

    @model_validator(mode="after")
    def validate_challenge_note(self) -> "EvaluationFeedback":
        if self.confirmed is False:
            if not self.challenge_note or not self.challenge_note.strip():
                raise ValueError("Challenge note is required.")
        return self


class DecisionRecord(BaseModel):
    decision_type: DecisionType
    rationale: str = Field(..., min_length=5, max_length=900)
    owner: str = Field(..., min_length=2, max_length=120)


class RiskCaseDraft(BaseModel):
    case_id: str = Field(..., min_length=6, max_length=64)
    version: int = Field(..., ge=1)
    policy_version: str
    created_at: datetime
    updated_at: datetime

    anchor: RiskAnchor
    definition: RiskDefinition
    likelihood: LikelihoodAssessment
    impact: ImpactAssessment

    evaluation_snapshot: Optional[EvaluationSnapshot] = None
    evaluation_feedback: Optional[EvaluationFeedback] = None
    decision: Optional[DecisionRecord] = None


def schema_json(model: type[BaseModel]) -> Dict[str, Any]:
    if hasattr(model, "model_json_schema"):
        return model.model_json_schema()  # type: ignore[attr-defined]
    return model.schema()  # type: ignore[no-any-return]
