from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from risk_decision.core.decision_types import (
    ActionItem,
    AuditFingerprint,
    DecisionContext,
    DecisionLevel,
    DecisionOutput,
    DomainDecision,
)


class ScoringComponent(Protocol):
    def score(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class AggregationComponent(Protocol):
    def aggregate(
        self,
        indicator_details: Dict[str, Any],
        local_scores: Dict[str, float],
    ) -> Dict[str, Any]:
        raise NotImplementedError


class ClassificationComponent(Protocol):
    def classify(self, domain_scores: Dict[str, float]) -> Dict[str, Any]:
        raise NotImplementedError


class RulesComponent(Protocol):
    def decide(self, classifications: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class ExplainabilityComponent(Protocol):
    def explain(
        self,
        classifications: Dict[str, Any],
        indicator_details: Dict[str, Any],
        local_scores: Dict[str, float],
    ) -> Dict[str, Any]:
        raise NotImplementedError


class AuditComponent(Protocol):
    def build_audit(
        self,
        decision_output: DecisionOutput,
        raw_parts: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError


@dataclass
class DecisionEngine:
    scorer: ScoringComponent
    aggregator: AggregationComponent
    classifier: ClassificationComponent
    rules: RulesComponent
    explainability: ExplainabilityComponent
    audit: Optional[AuditComponent] = None

    def run(self, context: DecisionContext, payload: Dict[str, Any]) -> DecisionOutput:
        score_parts = self.scorer.score(payload)
        indicator_details = score_parts.get("indicator_details", {}) or {}
        local_scores = score_parts.get("local_scores", {}) or {}

        agg_parts = self.aggregator.aggregate(indicator_details, local_scores)
        domain_scores = agg_parts.get("domain_scores", {}) or {}
        category_scores = agg_parts.get("category_scores", {}) or {}

        classifications = self.classifier.classify(domain_scores)

        decision_parts = self.rules.decide(classifications)
        overall = decision_parts.get("overall", DecisionLevel.CONDITIONAL)
        per_domain_levels = decision_parts.get("per_domain", {}) or {}
        rationale = decision_parts.get("rationale", []) or []
        required_actions = decision_parts.get("required_actions", []) or []

        expl_parts = self.explainability.explain(
            classifications, indicator_details, local_scores
        )
        top_contributors_by_domain = expl_parts.get(
            "top_contributors_by_domain", {}
        ) or {}

        per_domain: Dict[str, DomainDecision] = {}
        for domain, cls in classifications.items():
            level = per_domain_levels.get(domain, DecisionLevel.CONDITIONAL)
            score = float(cls.get("score", 0.0))
            classification_label = str(
                cls.get("level", cls.get("classification", ""))
            )

            per_domain[domain] = DomainDecision(
                domain=domain,
                level=level,
                score=score,
                classification=classification_label,
                rationale=[],
                top_contributors=top_contributors_by_domain.get(domain, []) or [],
            )

        action_items: list[ActionItem] = []
        for a in required_actions:
            if isinstance(a, ActionItem):
                action_items.append(a)
                continue
            if isinstance(a, dict):
                action_items.append(
                    ActionItem(
                        priority=int(a.get("priority", 1)),
                        action=str(a.get("action", "")).strip(),
                        deliverables=str(a.get("deliverables", "")).strip(),
                        owner=str(a.get("owner", "TBC")).strip() or "TBC",
                        target_date=str(a.get("target_date", "TBC")).strip() or "TBC",
                        related_domain=(
                            str(a.get("related_domain")).strip()
                            if a.get("related_domain")
                            else None
                        ),
                        related_controls=list(a.get("related_controls", []) or []),
                        evidence_expected=list(a.get("evidence_expected", []) or []),
                    )
                )

        output = DecisionOutput(
            context=context,
            overall=overall,
            per_domain=per_domain,
            domain_scores={
                k: (
                    {"score": float(v.get("score", 0.0)), "level": v.get("level", "")}
                    if isinstance(v, dict)
                    else {"score": float(v), "level": ""}
                )
                for k, v in domain_scores.items()
            }
            if isinstance(domain_scores, dict)
            else {},
            category_scores={
                str(k): float(v) for k, v in category_scores.items()
            }
            if isinstance(category_scores, dict)
            else {},
            rationale=[str(x) for x in rationale],
            required_actions=action_items,
            audit_trail=[],
            fingerprint=None,
        )

        if self.audit is not None:
            audit_result = self.audit.build_audit(
                decision_output=output,
                raw_parts={
                    "payload": payload,
                    "score_parts": score_parts,
                    "agg_parts": agg_parts,
                    "classifications": classifications,
                    "decision_parts": decision_parts,
                    "expl_parts": expl_parts,
                },
            )

            fingerprint = audit_result.get("fingerprint")
            if isinstance(fingerprint, dict):
                fingerprint = AuditFingerprint(
                    input_hash=str(fingerprint.get("input_hash", "")),
                    config_hash=str(fingerprint.get("config_hash", "")),
                    model_hash=str(fingerprint.get("model_hash", "")),
                )

            output = DecisionOutput(
                context=output.context,
                overall=output.overall,
                per_domain=output.per_domain,
                domain_scores=output.domain_scores,
                category_scores=output.category_scores,
                rationale=output.rationale,
                required_actions=output.required_actions,
                audit_trail=list(audit_result.get("audit_trail", []) or []),
                fingerprint=fingerprint,
                warnings=output.warnings,
                notes=output.notes,
            )

        return output

