from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from core.models import EvaluationSnapshot
from core.policy import PolicyConfig
from core.utils import get_nested, stable_hash

# Fields computed from other fields. Excluded from the hash so that inputs_hash
# answers "what was assessed", not "what was computed".
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
    """Apply policy overrides to a matrix category.

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


def escalation_reasons(
    draft_payload: Dict[str, Any],
    category: str,
    applied_overrides: List[str],
    policy: PolicyConfig,
) -> List[str]:
    """Why this case needs approval above the risk owner."""
    reasons: List[str] = []

    if category in policy.escalation_categories():
        reasons.append(f"Category is {category}.")

    if applied_overrides and policy.escalate_on_any_override():
        reasons.append(f"Policy override applied: {', '.join(applied_overrides)}.")

    floor = policy.escalation_confidence_floor()
    if floor is not None:
        weak = [
            dimension
            for dimension in ("likelihood", "impact")
            if int(get_nested(draft_payload, f"{dimension}.confidence") or 5) <= floor
        ]
        if weak:
            reasons.append(
                f"Confidence is {floor} or below for: {', '.join(weak)}. "
                "A weak evidence base does not lower the risk, it widens it."
            )

    return reasons


def accept_blockers(
    draft_payload: Dict[str, Any],
    category: str,
    policy: PolicyConfig,
) -> List[str]:
    """Reasons this case cannot be accepted by anyone, at any level."""
    blockers: List[str] = []

    hint = get_nested(draft_payload, "impact.acceptability_hint")
    if hint in policy.blocking_acceptability_hints():
        blockers.append(
            f"The assessor recorded the outcome as {hint}. "
            "Reduce, transfer or avoid it, or revise the assessment."
        )

    hard_block = policy.hard_accept_block_category()
    if hard_block and policy.category_rank(category) >= policy.category_rank(hard_block):
        blockers.append(f"A {category} risk cannot be accepted under this policy.")

    return blockers


def compute_snapshot(draft_payload: Dict[str, Any], policy: PolicyConfig) -> EvaluationSnapshot:
    likelihood_raw = int(get_nested(draft_payload, "likelihood.raw_value"))
    impact_raw = int(get_nested(draft_payload, "impact.raw_value"))

    base_category = policy.category_from_matrix(likelihood_raw, impact_raw)
    category, applied = apply_overrides(draft_payload, base_category, policy)

    reasons = escalation_reasons(draft_payload, category, applied, policy)

    return EvaluationSnapshot(
        created_at=_now_iso(),
        policy_version=policy.policy_version,
        likelihood_normalised=policy.normalise_likelihood(likelihood_raw),
        impact_normalised=policy.normalise_impact(impact_raw),
        overall_risk_score=policy.ordering_score(likelihood_raw, impact_raw),
        matrix_category=base_category,
        risk_category=category,
        recommended_decision=policy.recommend_decision(category),
        escalation_required=bool(reasons),
        escalation_reasons=reasons,
        applied_overrides=applied,
        accept_blockers=accept_blockers(draft_payload, category, policy),
        roles_that_may_accept=policy.roles_that_can_accept(category),
        inputs_hash=stable_hash(hashable_inputs(draft_payload)),
    )
