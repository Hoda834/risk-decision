from __future__ import annotations

from enum import Enum


class RiskDomain(str, Enum):
    DESIGN_MATURITY = "design_maturity"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    MEASUREMENT_INTEGRITY = "measurement_integrity"
    MANUFACTURING = "manufacturing"
    SUPPLY_CHAIN = "supply_chain"
    DATA_EVIDENCE = "data_evidence"
    DECISION_GOVERNANCE = "decision_governance"
