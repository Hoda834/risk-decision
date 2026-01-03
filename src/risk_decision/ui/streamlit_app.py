from __future__ import annotations

import sys
from pathlib import Path

# ---- FIX FOR STREAMLIT CLOUD (src layout) ----
SRC_PATH = Path(__file__).resolve().parents[2]
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
# --------------------------------------------

import json
from typing import Any, Dict

import streamlit as st

from risk_decision.core.decision_engine import DecisionEngine
from risk_decision.core.decision_types import DecisionContext
from risk_decision.engine.scorer import BasicScorer
from risk_decision.engine.aggregator import BasicAggregator
from risk_decision.engine.classifier import BasicClassifier
from risk_decision.engine.rules import BasicRules
from risk_decision.engine.explainability import BasicExplainability
from risk_decision.engine.audit_trail import BasicAuditTrail


def default_input() -> Dict[str, Any]:
    return {
        "context": {
            "decision_id": "demo",
            "title": "Risk-based decision demo",
            "activity": "product_design",
            "stage": "design",
        },
        "payload": {
            "indicator_details": {
                "i1": {"domain": "design_maturity", "category": "unvalidated_assumptions"},
                "i2": {"domain": "regulatory_compliance", "category": "documentation_gaps"},
                "i3": {"domain": "manufacturing", "category": "qc_gaps"},
            },
            "local_scores": {
                "i1": 10.0,
                "i2": 50.0,
                "i3": 30.0,
            },
        },
    }


def build_engine(low: float, high: float) -> DecisionEngine:
    return DecisionEngine(
        scorer=BasicScorer(),
        aggregator=BasicAggregator(),
        classifier=BasicClassifier(low_threshold=low, high_threshold=high),
        rules=BasicRules(),
        explainability=BasicExplainability(),
        audit=BasicAuditTrail(),
    )


def main() -> None:
    st.set_page_config(page_title="Risk-Decision", layout="wide")
    st.title("Risk-Decision")

    with st.sidebar:
        st.subheader("Thresholds")
        low = st.number_input("Low threshold", value=20.0)
        high = st.number_input("High threshold", value=45.0)

    if "json_input" not in st.session_state:
        st.session_state.json_input = json.dumps(default_input(), indent=2)

    text = st.text_area("Input JSON", value=st.session_state.json_input, height=400)

    col1, col2 = st.columns(2)
    run = col1.button("Run decision")
    reset = col2.button("Reset demo")

    if reset:
        st.session_state.json_input = json.dumps(default_input(), indent=2)
        st.experimental_rerun()

    if not run:
        st.info("Click Run decision to execute the decision engine.")
        return

    try:
        raw = json.loads(text)
    except Exception as e:
        st.error(f"Invalid JSON: {e}")
        return

    ctx = raw.get("context", {})
    payload = raw.get("payload", {})

    context = DecisionContext(
        decision_id=str(ctx.get("decision_id", "decision")),
        title=str(ctx.get("title", "")),
        activity=str(ctx.get("activity", "")),
        stage=str(ctx.get("stage", "")),
    )

    engine = build_engine(low, high)
    output = engine.run(context=context, payload=payload)

    st.subheader("Overall decision")
    st.metric("Decision", output.overall.value)

    st.subheader("Per-domain decisions")
    st.dataframe(
        [
            {
                "domain": d,
                "decision": dd.level.value,
                "score": dd.score,
                "classification": dd.classification,
            }
            for d, dd in output.per_domain.items()
        ],
        use_container_width=True,
    )

    st.subheader("Required actions")
    if output.required_actions:
        st.dataframe(
            [
                {
                    "priority": a.priority,
                    "action": a.action,
                    "domain": a.related_domain,
                }
                for a in output.required_actions
            ],
            use_container_width=True,
        )
    else:
        st.write("No actions required.")

    st.subheader("Audit & fingerprint")
    st.json(
        {
            "audit_trail": output.audit_trail,
            "fingerprint": {
                "input_hash": output.fingerprint.input_hash if output.fingerprint else "",
                "config_hash": output.fingerprint.config_hash if output.fingerprint else "",
                "model_hash": output.fingerprint.model_hash if output.fingerprint else "",
            }
            if output.fingerprint
            else {},
        }
    )


if __name__ == "__main__":
    main()
