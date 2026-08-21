from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class IndicatorResponse:
    indicator_id: str
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionPayload:
    indicator_details: Dict[str, Dict[str, Any]]
    local_scores: Dict[str, float]
    responses: List[IndicatorResponse] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
