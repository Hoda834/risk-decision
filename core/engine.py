from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from core.models import EvaluationSnapshot
from core.policy import PolicyConfig
from core.utils import stable_hash


def compute_snapshot(draft_payload: Dict[str, Any], policy: PolicyConfig) -> EvaluationSnapshot:
    likelihood_raw = int(draft_payload["likelihood"]["raw_value"])
    impact_raw = int(draft_payload["impact"]["raw_value"])

    lnorm = policy.normalise_likelihood(likelihood_raw)
    inorm = policy.normalise_impact(impact_raw)

    score = policy.score(lnorm, inorm)
    category = policy.classify(score)

    inputs_for_hash = {
        "anchor": draft_payload.get("anchor"),
        "definition": draft_payload.get("definition"),
        "likelihood": {"raw_value": likelihood_raw, "basis": draft_payload["likelihood"].get("basis")},
        "impact": {
            "raw_value": impact_raw,
            "domains": draft_payload["impact"].get("domains"),
            "reversibility": draft_payload["impact"].get("reversibility"),
            "acceptability_hint": draft_payload["impact"].get("acceptability_hint"),
            "worst_credible_outcome": draft_payload["impact"].get("worst_credible_outcome"),
        },
    }

    return EvaluationSnapshot(
        policy_version=policy.policy_version,
        created_at=datetime.now(timezone.utc).isoformat(),
        overall_risk_score=score,
        risk_category=category,
        inputs_hash=stable_hash(inputs_for_hash),
    )


def acceptance_requires_escalation(snapshot: EvaluationSnapshot, policy: PolicyConfig) -> bool:
    return float(snapshot.overall_risk_score) >= float(policy.acceptance_threshold())
