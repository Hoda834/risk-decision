from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from core.models import EvaluationSnapshot
from core.policy import PolicyConfig
from core.utils import get_nested, stable_hash

# Fields that are computed from other fields. They are excluded from the hash so
# that inputs_hash answers "what was assessed", not "what was computed".
DERIVED_FIELDS = ("normalised",)

ASSESSED_LIKELIHOOD_FIELDS = ("raw_value", "basis", "confidence", "signals")
ASSESSED_IMPACT_FIELDS = (
    "raw_value",
    "domains",
    "reversibility",
    "acceptability_hint",
    "worst_credible_outcome",
    "confidence",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _subset(source: Any, fields: Tuple[str, ...]) -> Dict[str, Any]:
    data = source if isinstance(source, dict) else {}
    return {f: data.get(f) for f in fields if f in data}


def hashable_inputs(draft_payload: Dict[str, Any]) -> Dict[str, Any]:
    """The assessed inputs only. Derived values are excluded by construction."""
    return {
        "anchor": draft_payload.get("anchor"),
        "definition": draft_payload.get("definition"),
        "likelihood": _subset(draft_payload.get("likelihood"), ASSESSED_LIKELIHOOD_FIELDS),
        "impact": _subset(draft_payload.get("impact"), ASSESSED_IMPACT_FIELDS),
    }


def apply_overrides(
    draft_payload: Dict[str, Any],
    category: str,
    policy: PolicyConfig,
) -> Tuple[str, List[str]]:
    """Apply policy overrides to a computed category.

    Overrides can only raise a category, never lower it. Every one that fires is
    named in the snapshot so the reader can see why the category moved.
    """
    applied: List[str] = []
    effective = category

    for name, rule in policy.overrides().items():
        fired = False

        level_gte = rule.get("if_impact_level_gte")
        if level_gte is not None:
            raw = get_nested(draft_payload, "impact.raw_value")
            if raw is not None and int(raw) >= int(level_gte):
                fired = True

        reversibility_in = rule.get("if_reversibility_in")
        if reversibility_in:
            value = get_nested(draft_payload, "impact.reversibility")
            if value in set(reversibility_in):
                fired = True

        text_contains = rule.get("if_text_contains")
        if text_contains:
            haystack = " ".join(
                str(get_nested(draft_payload, path) or "").lower()
                for path in rule.get("search_paths", [])
            )
            if any(str(word).lower() in haystack for word in text_contains):
                fired = True

        if fired:
            applied.append(name)
            effective = policy.floor_category(effective, rule.get("floor_category"))

    return effective, applied


def requires_escalation(score: float, applied_overrides: List[str], policy: PolicyConfig) -> bool:
    if float(score) >= policy.escalation_score_threshold():
        return True
    return bool(applied_overrides) and policy.escalate_on_any_override()


def compute_snapshot(draft_payload: Dict[str, Any], policy: PolicyConfig) -> EvaluationSnapshot:
    likelihood_raw = int(get_nested(draft_payload, "likelihood.raw_value"))
    impact_raw = int(get_nested(draft_payload, "impact.raw_value"))

    likelihood_norm = policy.normalise_likelihood(likelihood_raw)
    impact_norm = policy.normalise_impact(impact_raw)
    score = policy.score(likelihood_norm, impact_norm)

    category, applied = apply_overrides(draft_payload, policy.classify(score), policy)

    return EvaluationSnapshot(
        created_at=_now_iso(),
        policy_version=policy.policy_version,
        likelihood_normalised=likelihood_norm,
        impact_normalised=impact_norm,
        overall_risk_score=score,
        risk_category=category,
        recommended_decision=policy.recommend_decision(category),
        escalation_required=requires_escalation(score, applied, policy),
        applied_overrides=applied,
        inputs_hash=stable_hash(hashable_inputs(draft_payload)),
    )


def acceptance_requires_escalation(snapshot: EvaluationSnapshot, policy: PolicyConfig) -> bool:
    return float(snapshot.overall_risk_score) >= policy.acceptance_threshold()
