from __future__ import annotations

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


APP_TITLE = "Risk-Decision"


def _default_input() -> Dict[str, Any]:
    return {
        "context": {
            "decision_id": "demo",
            "title": "Demo risk-based decision",
            "activity": "product_design",
            "stage": "design",
            "objective": "Decide whether to proceed",
            "risk_appetite": "medium",
            "constraints": "",
            "time_horizon": "",
            "metadata": {},
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


def _build_engine(low_threshold: float, high_threshold: float) -> DecisionEngine:
    return DecisionEngine(
        scorer=BasicScorer(),
        aggregator=BasicAggregator(),
        classifier=BasicClassifier(low_threshold=low_threshold, high_threshold=high_threshold),
        rules=BasicRules(),
        explainability=BasicExplainability(),
        audit=BasicAuditTrail(),
    )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    with st.sidebar:
        st.subheader("Thresholds")
        low_threshold = st.number_input("Low threshold", value=20.0, min_value=0.0, step=1.0)
        high_threshold = st.number_input("High threshold", value=45.0, min_value=0.0, step=1.0)

        st.divider()
        st.subheader("Input")
        st.caption("Paste a JSON object with keys: context, payload")

    if "input_json" not in st.session_state:
        st.session_state.input_json = json.dumps(_default_input(), ensure_ascii=False, indent=2)

    input_text = st.text_area("Input JSON", value=st.session_state.input_json, height=420)

    c_run, c_reset = st.columns([1, 1])
    with c_run:
        run = st.button("Run decision")
    with c_reset:
        reset = st.button("Reset demo input")

    if reset:
        st.session_state.input_json = json.dumps(_default_input(), ensure_ascii=False, indent=2)
        st.rerun()

    if not run:
        st.info("Click Run decision to generate a decision output.")
        return

    try:
        raw = json.loads(input_text)
    except Exception as e:
        st.error(f"Invalid JSON. Error: {e}")
        return

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

    engine = _build_engine(low_threshold=low_threshold, high_threshold=high_threshold)
    output = engine.run(context=context, payload=payload)

    st.divider()
    st.subheader("Decision summary")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Overall decision", output.overall.value)
    with col2:
        st.write("Decision ID")
        st.code(output.context.decision_id)
    with col3:
        st.write("Title")
        st.write(output.context.title)

    st.divider()
    st.subheader("Per-domain view")

    rows = []
    for d, dd in output.per_domain.items():
        rows.append(
            {
                "Domain": d,
                "Decision": dd.level.value,
                "Score": dd.score,
                "Classification": dd.classification,
                "Top contributors": len(dd.top_contributors),
            }
        )

    st.dataframe(rows, use_container_width=True)

    st.divider()
    st.subheader("Top contributors (by domain)")
    st.json({d: output.per_domain[d].top_contributors for d in output.per_domain})

    st.divider()
    st.subheader("Required actions")
    if output.required_actions:
        st.dataframe(
            [
                {
                    "priority": a.priority,
                    "action": a.action,
                    "deliverables": a.deliverables,
                    "owner": a.owner,
                    "target_date": a.target_date,
                    "related_domain": a.related_domain,
                }
                for a in output.required_actions
            ],
            use_container_width=True,
        )
    else:
        st.write("No required actions produced.")

    st.divider()
    st.subheader("Audit trail and fingerprints")
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
