from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

SRC_PATH = Path(__file__).resolve().parents[2]
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

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
            "title": "Proceed decision for early-stage development",
            "activity": "product_design",
            "stage": "design",
            "objective": "Decide whether to proceed to the next phase",
            "risk_appetite": "medium",
            "constraints": "",
            "time_horizon": "4 weeks",
            "metadata": {},
        },
        "payload": {
            "indicator_details": {
                "i1": {"domain": "design_maturity", "category": "unvalidated_assumptions"},
                "i2": {"domain": "regulatory_compliance", "category": "documentation_gaps"},
                "i3": {"domain": "manufacturing", "category": "qc_gaps"},
                "i4": {"domain": "supply_chain", "category": "single_source_supplier"},
            },
            "local_scores": {
                "i1": 12.0,
                "i2": 48.0,
                "i3": 28.0,
                "i4": 52.0,
            },
        },
    }


def _build_engine(low: float, high: float) -> DecisionEngine:
    return DecisionEngine(
        scorer=BasicScorer(),
        aggregator=BasicAggregator(),
        classifier=BasicClassifier(low_threshold=low, high_threshold=high),
        rules=BasicRules(),
        explainability=BasicExplainability(),
        audit=BasicAuditTrail(),
    )


def _decision_badge(decision_value: str) -> str:
    v = (decision_value or "").strip().lower()
    if v == "approve":
        return "APPROVE"
    if v == "conditional":
        return "CONDITIONAL APPROVAL"
    if v == "reject":
        return "DO NOT PROCEED"
    return v.upper() if v else "UNKNOWN"


def _render_key_points(output) -> List[str]:
    points: List[str] = []

    rejects = [d for d, dd in output.per_domain.items() if dd.level.value == "reject"]
    conditionals = [d for d, dd in output.per_domain.items() if dd.level.value == "conditional"]

    if rejects:
        points.append("High-risk domains require mitigation before proceeding: " + ", ".join(sorted(rejects)))
    if conditionals:
        points.append("Medium-risk domains require conditions: " + ", ".join(sorted(conditionals)))
    if not rejects and not conditionals:
        points.append("No blocking risks identified based on current thresholds.")

    if output.fingerprint:
        points.append("Decision is reproducible via input and config fingerprints.")

    return points


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    with st.sidebar:
        st.subheader("Thresholds")
        low = st.number_input("Low threshold", value=20.0, min_value=0.0, step=1.0)
        high = st.number_input("High threshold", value=45.0, min_value=0.0, step=1.0)

        st.divider()
        st.subheader("Input")
        st.caption("Paste a JSON object with keys: context, payload")

    if "input_json" not in st.session_state:
        st.session_state.input_json = json.dumps(_default_input(), ensure_ascii=False, indent=2)

    input_text = st.text_area("Input JSON", value=st.session_state.input_json, height=360)

    c1, c2 = st.columns([1, 1])
    run = c1.button("Run decision")
    reset = c2.button("Reset demo input")

    if reset:
        st.session_state.input_json = json.dumps(_default_input(), ensure_ascii=False, indent=2)
        st.rerun()

    if not run:
        st.info("Click Run decision to generate a decision output.")
        return

    try:
        raw = json.loads(input_text)
    except Exception as e:
        st.error(f"Invalid JSON: {e}")
        return

    ctx = raw.get("context", {}) or {}
    payload = raw.get("payload", {}) or {}

    context = DecisionContext(
        decision_id=str(ctx.get("decision_id", "decision")),
        title=str(ctx.get("title", "Risk-based decision")),
        activity=str(ctx.get("activity", "")),
        stage=str(ctx.get("stage", "")),
        objective=str(ctx.get("objective", "")),
        risk_appetite=str(ctx.get("risk_appetite", "medium")),
        constraints=str(ctx.get("constraints", "")),
        time_horizon=str(ctx.get("time_horizon", "")),
        metadata=dict(ctx.get("metadata", {}) or {}),
    )

    engine = _build_engine(low=low, high=high)
    output = engine.run(context=context, payload=payload)

    st.divider()
    st.subheader("Decision outcome")

    col_a, col_b, col_c = st.columns([1, 2, 2])
    with col_a:
        st.metric("Outcome", _decision_badge(output.overall.value))
    with col_b:
        st.write("Decision ID")
        st.code(output.context.decision_id)
    with col_c:
        st.write("Title")
        st.write(output.context.title)

    st.divider()
    st.subheader("Executive summary")

    points = _render_key_points(output)
    for p in points:
        st.write(f"- {p}")

    st.divider()
    st.subheader("Per-domain decisions")

    domain_rows = []
    for d, dd in output.per_domain.items():
        domain_rows.append(
            {
                "Domain": d,
                "Decision": dd.level.value,
                "Score": dd.score,
                "Classification": dd.classification,
                "Top contributors": len(dd.top_contributors),
            }
        )

    st.dataframe(domain_rows, width="stretch")

    st.divider()
    st.subheader("Top contributors")

    st.json({d: output.per_domain[d].top_contributors for d in output.per_domain})

    st.divider()
    st.subheader("Required actions")

    if output.required_actions:
        action_rows = []
        for a in output.required_actions:
            action_rows.append(
                {
                    "Priority": a.priority,
                    "Action": a.action,
                    "Domain": a.related_domain or "",
                    "Owner": a.owner,
                    "Target date": a.target_date,
                }
            )
        st.dataframe(action_rows, width="stretch")
    else:
        st.write("No required actions produced.")

    st.divider()
    st.subheader("Audit and reproducibility")

    st.json(
        {
            "fingerprint": {
                "input_hash": output.fingerprint.input_hash if output.fingerprint else "",
                "config_hash": output.fingerprint.config_hash if output.fingerprint else "",
                "model_hash": output.fingerprint.model_hash if output.fingerprint else "",
            }
            if output.fingerprint
            else {},
            "audit_trail": output.audit_trail,
        }
    )


if __name__ == "__main__":
    main()
