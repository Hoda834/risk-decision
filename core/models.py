from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AnchorType(str, Enum):
    PROBLEM = "Problem"
    OPPORTUNITY = "Opportunity"
    DECISION = "Decision"


class Direction(str, Enum):
    NEGATIVE = "Negative"
    POSITIVE = "Positive"
    MIXED = "Mixed"


class LikelihoodBasis(str, Enum):
    EXPERT_JUDGEMENT = "Expert judgement"
    HISTORICAL_DATA = "Historical data"
    BENCHMARKING = "Benchmarking"
    SIMULATION = "Simulation"


class ImpactDomain(str, Enum):
    FINANCIAL = "Financial"
    OPERATIONAL = "Operational"
    REGULATORY = "Regulatory"
    REPUTATIONAL = "Reputational"
    SAFETY = "Safety"


class Reversibility(str, Enum):
    REVERSIBLE = "Reversible"
    PARTIALLY_REVERSIBLE = "Partially reversible"
    IRREVERSIBLE = "Irreversible"


class AcceptabilityHint(str, Enum):
    ACCEPTABLE = "Acceptable"
    TOLERABLE = "Tolerable"
    NOT_ACCEPTABLE = "Not acceptable"


class DecisionType(str, Enum):
    ACCEPT = "ACCEPT"
    REDUCE = "REDUCE"
    TRANSFER = "TRANSFER"
    AVOID = "AVOID"
    DEFER = "DEFER"


class _Strict(BaseModel):
    """Unknown keys are an error, not something to drop quietly.

    A silent drop is how an override note goes missing without anyone
    noticing, which defeats the point of an audit trail.
    """

    model_config = ConfigDict(extra="forbid")


class RiskAnchor(_Strict):
    anchor_type: AnchorType = Field(..., description="The anchor type for the risk case.")
    name: str = Field(..., min_length=1, description="A human friendly case name.")
    value_statement: str = Field(..., min_length=1, description="What value is at stake.")
    owner: str = Field(..., min_length=1, description="Owner of the risk case.")
    direction: Direction = Field(default=Direction.NEGATIVE, description="Downside, upside or both.")


class RiskDefinition(_Strict):
    event: str = Field(..., min_length=1, description="What could happen.")
    triggers: List[str] = Field(..., min_length=1, description="Triggers or leading events.")
    cause_categories: List[str] = Field(..., min_length=1, description="Cause categories.")
    vulnerability: str = Field(..., min_length=1, description="Why this is exposed.")
    consequences: str = Field(..., min_length=1, description="Consequences summary.")
    time_to_impact_months: int = Field(..., ge=0, description="Time to impact in months.")
    scope: str = Field(..., min_length=1, description="What is in scope.")
    assumptions: str = Field(..., min_length=1, description="Assumptions.")
    data_used: str = Field(..., min_length=1, description="Data used.")
    references: str = Field(..., min_length=1, description="References.")


class LikelihoodAssessment(_Strict):
    basis: LikelihoodBasis = Field(..., description="Basis used to assess likelihood.")
    signals: List[str] = Field(default_factory=list, description="Signals to watch.")
    raw_value: int = Field(..., ge=1, le=5, description="Raw likelihood score 1-5.")
    normalised: float = Field(default=0.0, ge=0.0, le=1.0, description="Normalised likelihood 0-1.")
    confidence: int = Field(..., ge=1, le=5, description="Confidence 1-5.")


class ImpactAssessment(_Strict):
    domains: List[ImpactDomain] = Field(default_factory=list, description="Impact domains.")
    worst_credible_outcome: str = Field(..., min_length=1, description="Worst credible outcome.")
    reversibility: Reversibility = Field(..., description="Reversibility.")
    raw_value: int = Field(..., ge=1, le=5, description="Raw impact severity 1-5.")
    normalised: float = Field(default=0.0, ge=0.0, le=1.0, description="Normalised impact 0-1.")
    confidence: int = Field(..., ge=1, le=5, description="Confidence 1-5.")
    acceptability_hint: AcceptabilityHint = Field(..., description="Acceptability hint.")


class EvaluationSnapshot(_Strict):
    """Immutable record of one evaluation under one policy version."""

    created_at: str = Field(..., description="UTC ISO timestamp of evaluation.")
    policy_version: str = Field(..., description="Policy version used.")
    likelihood_normalised: float = Field(..., ge=0.0, le=1.0)
    impact_normalised: float = Field(..., ge=0.0, le=1.0)
    overall_risk_score: float = Field(..., ge=0.0, le=1.0, description="Overall risk score 0-1.")
    risk_category: str = Field(..., description="Category after any policy overrides.")
    recommended_decision: DecisionType = Field(..., description="Decision the policy recommends.")
    escalation_required: bool = Field(default=False)
    applied_overrides: List[str] = Field(default_factory=list)
    inputs_hash: str = Field(..., description="SHA-256 over the assessed inputs only.")


class DecisionRecord(_Strict):
    decision_type: DecisionType = Field(..., description="Decision category.")
    rationale: str = Field(..., min_length=1, description="Why this decision.")
    owner: str = Field(..., min_length=1, description="Owner.")
    follows_recommendation: bool = Field(default=True, description="False when the policy was overridden.")
    override_note: str = Field(default="", description="Reason recorded for an override.")


class EvaluationFeedback(_Strict):
    messages: List[str] = Field(default_factory=list, description="Feedback messages.")


class WizardState(_Strict):
    state: str = Field(default="anchor")
    locked_at_end: bool = Field(default=False)


class RiskCaseDraft(_Strict):
    case_id: str = Field(..., min_length=1)
    version: int = Field(..., ge=1)
    anchor: RiskAnchor
    definition: RiskDefinition
    likelihood: LikelihoodAssessment
    impact: ImpactAssessment
    wizard: Optional[WizardState] = None
    evaluation_snapshot: Optional[Dict[str, Any]] = None
    decision: Optional[Dict[str, Any]] = None
    feedback: Optional[Dict[str, Any]] = None
