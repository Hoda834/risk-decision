from __future__ import annotations

from typing import Any, Dict, List

from risk_decision.core.decision_types import DecisionOutput
from risk_decision.core.fingerprints import build_fingerprints


class BasicAuditTrail:
    def build_audit(
        self,
        decision_output: DecisionOutput,
        raw_parts: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = raw_parts.get("payload", {}) or {}
        config = {
            "rules": raw_parts.get("decision_parts", {}),
            "classification": raw_parts.get("classifications", {}),
        }

        fingerprint = build_fingerprints(
            payload=payload,
            config=config,
            model_ref="risk-decision",
        )

        audit_entries: List[Dict[str, Any]] = []

        audit_entries.append(
            {
                "key": "overall_decision",
                "value": decision_output.overall.value,
            }
        )

        audit_entries.append(
            {
                "key": "per_domain_decision",
                "value": {
                    d: decision_output.per_domain[d].level.value
                    for d in decision_output.per_domain
                },
            }
        )

        audit_entries.append(
            {
                "key": "domain_scores",
                "value": decision_output.domain_scores,
            }
        )

        return {
            "audit_trail": audit_entries,
            "fingerprint": fingerprint,
        }
