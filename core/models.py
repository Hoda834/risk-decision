from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RiskAnchor(BaseModel):
    """
    Draft-friendly anchor model.
    Empty strings are allowed at draft stage.
    Step-level checks should be enforced by the wizard / UI.
    """

    model_config = ConfigDict(extra="allow")

    name: str = ""
    anchor_type: Literal["asset", "process", "organisation", "other"] = "asset"
    description: str = ""
    domains: List[str] = Field(default_factory=list)


class RiskDefinition(BaseModel):
    """
    Draft-friendly definition model.
    """

    model_config = ConfigDict(extra="allow")

    event: str = ""
    causes: List[str] = Field(default_factory=list)
    consequences: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    stakeholders: List[str] = Field(default_factory=list)


class RiskLikelihood(BaseModel):
    """
    Draft-friendly likelihood model.
    """

    model_config = ConfigDict(extra="allow")

    raw_value: int = 1
    normalised: float = 0.0
    evidence_source: str = ""
    notes: str = ""


class RiskImpact(BaseModel):
    """
    Draft-friendly impact model.
    """

    model_config = ConfigDict(extra="allow")

    raw_value: int = 1
    normalised: float = 0.0
    worst_credible_outcome: str = ""
    notes: str = ""


class RiskCaseDraft(BaseModel):
    """
    Draft model used for storage and iterative editing.

    Intentionally permissive so a new case can be created with placeholders,
    then completed step-by-step in Streamlit.
    """

    model_config = ConfigDict(extra="allow")

    case_id: str
    case_name: str = ""
    version: int

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    policy_id: str = ""
    policy_version: str = ""

    anchor: RiskAnchor = Field(default_factory=RiskAnchor)
    definition: RiskDefinition = Field(default_factory=RiskDefinition)
    likelihood: RiskLikelihood = Field(default_factory=RiskLikelihood)
    impact: RiskImpact = Field(default_factory=RiskImpact)

    # Stored and edited by the app, keep them flexible but persistent.
    decision: Dict[str, Any] = Field(default_factory=dict)
    mitigations: List[Dict[str, Any]] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)

    def touch(self) -> "RiskCaseDraft":
        self.updated_at = utc_now()
        return self
