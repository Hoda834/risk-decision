from risk_decision.core.decision_engine import DecisionEngine
from risk_decision.core.decision_types import DecisionContext
from risk_decision.engine.scorer import BasicScorer
from risk_decision.engine.aggregator import BasicAggregator
from risk_decision.engine.classifier import BasicClassifier
from risk_decision.engine.rules import BasicRules
from risk_decision.engine.explainability import BasicExplainability
from risk_decision.engine.audit_trail import BasicAuditTrail


def test_decision_engine_runs():
    engine = DecisionEngine(
        scorer=BasicScorer(),
        aggregator=BasicAggregator(),
        classifier=BasicClassifier(),
        rules=BasicRules(),
        explainability=BasicExplainability(),
        audit=BasicAuditTrail(),
    )

    context = DecisionContext(
        decision_id="test",
        title="Test decision",
        activity="product_design",
        stage="design",
    )

    payload = {
        "indicator_details": {
            "i1": {"domain": "design_maturity", "category": "unvalidated_assumptions"},
            "i2": {"domain": "regulatory_compliance", "category": "documentation_gaps"},
        },
        "local_scores": {
            "i1": 10.0,
            "i2": 50.0,
        },
    }

    output = engine.run(context=context, payload=payload)

    assert output.overall.value in {"approve", "conditional", "reject"}
    assert "design_maturity" in output.per_domain
