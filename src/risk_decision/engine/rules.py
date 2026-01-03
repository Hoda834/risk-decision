from __future__ import annotations

from typing import Dict, List

from risk_decision.core.decision_types import ActionItem, DecisionLevel


class BasicRules:
    def decide(self, classifications: Dict[str, Dict[str, float | str]]) -> Dict[str, object]:
        per_domain: Dict[str, DecisionLevel] = {}
        rationale: List[str] = []
        required_actions: List[ActionItem] = []

        has_high = False
        has_medium = False

        for domain, info in classifications.items():
            level = str(info.get("level", ""))

            if level == "high":
                per_domain[domain] = DecisionLevel.REJECT
                has_high = True
                rationale.append(f"High risk detected in domain: {domain}")
                required_actions.append(
                    ActionItem(
                        priority=1,
                        action=f"Mitigate high risk in domain {domain}",
                        related_domain=domain,
                    )
                )
            elif level == "medium":
                per_domain[domain] = DecisionLevel.CONDITIONAL
                has_medium = True
                rationale.append(f"Medium risk requires conditions in domain: {domain}")
                required_actions.append(
                    ActionItem(
                        priority=2,
                        action=f"Reduce medium risk in domain {domain}",
                        related_domain=domain,
                    )
                )
            else:
                per_domain[domain] = DecisionLevel.APPROVE

        if has_high:
            overall = DecisionLevel.REJECT
        elif has_medium:
            overall = DecisionLevel.CONDITIONAL
        else:
            overall = DecisionLevel.APPROVE

        return {
            "overall": overall,
            "per_domain": per_domain,
            "rationale": rationale,
            "required_actions": required_actions,
        }
