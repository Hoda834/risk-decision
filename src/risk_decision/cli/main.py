from __future__ import annotations

import json
import sys
from typing import Any, Dict

from risk_decision.core.decision_engine import DecisionEngine
from risk_decision.core.decision_types import DecisionContext
from risk_decision.engine.scorer import BasicScorer
from risk_decision.engine.aggregator import BasicAggregator
from risk_decision.engine.classifier import BasicClassifier, PolicyAwareClassifier
from risk_decision.engine.rules import BasicRules
from risk_decision.engine.explainability import BasicExplainability
from risk_decision.engine.audit_trail import BasicAuditTrail


def _load_input(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python -m risk_decision.cli.main <input.json>\n")
        return 2

    input_path = sys.argv[1]
    raw = _load_input(input_path)

    context_data = raw.get("context", {}) or {}
    payload = raw.get("payload", {}) or {}

    context = DecisionContext(
        decision_id=str(context_data.get("decision_id", "decision")),
        title=str(context_data.get("title", "Risk-based decision")),
        activity=str(context_data.get("activity", "")),
        stage=str(context_data.get("stage", "")),
        objective=str(context_data.get("objective", "")),
        risk_appetite=str(context_data.get("risk_appetite", "medium")),
        constraints=str(context_data.get("constraints", "")),
        time_horizon=str(context_data.get("time_horizon", "")),
        metadata=dict(context_data.get("metadata", {}) or {}),
    )

    risk_appetite = context.risk_appetite.strip().lower() or "medium"
    stage = context.stage.strip().lower() or None

    classifier = PolicyAwareClassifier(
        base_low_threshold=20.0,
        base_high_threshold=45.0,
        risk_appetite=risk_appetite,
        stage=stage,
    )

    engine = DecisionEngine(
        scorer=BasicScorer(),
        aggregator=BasicAggregator(),
        classifier=classifier,
        rules=BasicRules(),
        explainability=BasicExplainability(),
        audit=BasicAuditTrail(),
    )

    output = engine.run(context=context, payload=payload)

    result = {
        "context": {
            "decision_id": output.context.decision_id,
            "title": output.context.title,
            "activity": output.context.activity,
            "stage": output.context.stage,
            "risk_appetite": output.context.risk_appetite,
        },
        "overall_decision": output.overall.value,
        "per_domain": {
            d: {
                "level": output.per_domain[d].level.value,
                "score": output.per_domain[d].score,
                "classification": output.per_domain[d].classification,
                "top_contributors": output.per_domain[d].top_contributors,
            }
            for d in output.per_domain
        },
        "rationale": output.rationale,
        "required_actions": [
            {
                "priority": a.priority,
                "action": a.action,
                "deliverables": a.deliverables,
                "owner": a.owner,
                "target_date": a.target_date,
                "related_domain": a.related_domain,
                "related_controls": a.related_controls,
                "evidence_expected": a.evidence_expected,
            }
            for a in output.required_actions
        ],
        "audit": {
            "trail": output.audit_trail,
            "fingerprint": {
                "input_hash": output.fingerprint.input_hash if output.fingerprint else "",
                "config_hash": output.fingerprint.config_hash if output.fingerprint else "",
                "model_hash": output.fingerprint.model_hash if output.fingerprint else "",
            }
            if output.fingerprint
            else {},
        },
    }

    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
