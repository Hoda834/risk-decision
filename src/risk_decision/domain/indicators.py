from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from risk_decision.domain.domains import RiskDomain
from risk_decision.domain.categories import RiskCategory


@dataclass(frozen=True)
class Indicator:
    indicator_id: str
    domain: RiskDomain
    category: RiskCategory
    description: str
    metadata: Dict[str, Any] | None = None
