from risk_decision.engine.rules import BasicRules
from risk_decision.core.decision_types import DecisionLevel


def test_rules_produce_overall_decision():
    rules = BasicRules()

    classifications = {
        "design_maturity": {"score": 10.0, "level": "low"},
        "regulatory_compliance": {"score": 60.0, "level": "high"},
    }

    result = rules.decide(classifications)

    assert result["overall"] == DecisionLevel.REJECT
    assert result["per_domain"]["regulatory_compliance"] == DecisionLevel.REJECT
