from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Tuple

from core.models import EvaluationSnapshot, RiskCaseDraft
from core.policy import PolicyConfig
from core.utils import stable_hash


def compute_snapshot(draft_payload: Dict[str, Any], policy: PolicyConfig) -> EvaluationSnapshot:
    likelihood_raw = int(draft_payload["likelihood"]["raw_value"])
    impact_raw = int(draft_payload["impact"]["raw_value"])

    lnorm = policy.normalise_likelihood(likelihood_raw)
    inorm = policy.normalise_impact(impact_raw)

    score = policy.score(lnorm, inorm)
    category = policy.classify(score)
    rec = policy.recommend_decision(score)

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
        created_at=datetime.utcnow(),
        likelihood_normalised=lnorm,
        impact_normalised=inorm,
        score=score,
        category=category,
        recommended_decision=rec,
        inputs_hash=stable_hash(inputs_for_hash),
    )


def acceptance_requires_escalation(snapshot: EvaluationSnapshot, policy: PolicyConfig) -> bool:
    return float(snapshot.score) >= float(policy.acceptance_threshold())
