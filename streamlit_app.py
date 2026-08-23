from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.models import DecisionRecord, DecisionType
from core.policy import PolicyConfig, load_policy
from core.questions import Question, load_question_bank
from core.storage import (
    StoragePaths,
    append_audit,
    init_case_paths,
    list_cases,
    read_draft,
    write_case_meta,
    write_decision,
    write_draft,
    write_snapshot,
)
from core.utils import get_nested
from core.wizard import (
    WizardStateEnum,
    apply_answer,
    compute_and_lock_snapshot,
    get_state,
    initial_payload,
    is_locked,
    next_state,
    outstanding_steps,
    prev_state,
    questions_for_state,
    set_state,
    step_errors,
    try_make_draft_model,
    validate_answer,
)

APP_TITLE = "Risk Decision Wizard"


@st.cache_resource
def _policy() -> PolicyConfig:
    return load_policy()


@st.cache_resource
def _questions() -> List[Question]:
    return load_question_bank(policy=_policy())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _case_label(case_item: Dict[str, Any]) -> str:
    case_id = case_item.get("case_id", "unknown")
    name = str(case_item.get("case_name") or "").strip() or "Untitled case"
    return f"{name} ({case_id})"


def _paths() -> StoragePaths:
    return st.session_state["paths"]


def _save(payload: Dict[str, Any], reason: str) -> None:
    """Persist the current version. Version numbers track evaluations, not clicks."""
    case_id = str(payload["case_id"])
    version = int(payload.get("version", 1))

    write_draft(_paths(), case_id, version, payload)

    anchor = payload.get("anchor") if isinstance(payload.get("anchor"), dict) else {}
    write_case_meta(
        _paths(),
        case_id,
        {
            "case_name": (anchor.get("name") or "Untitled case"),
            "owner": anchor.get("owner") or "",
            "updated_at": _now_iso(),
            "latest_version": version,
            "state": get_state(payload).value,
        },
    )

    event: Dict[str, Any] = {"action": reason, "version": version}
    snapshot = payload.get("evaluation_snapshot")
    if isinstance(snapshot, dict):
        event["inputs_hash"] = snapshot.get("inputs_hash")
        event["policy_version"] = snapshot.get("policy_version")
    append_audit(_paths(), case_id, event)


def _new_case() -> None:
    payload = initial_payload(_policy())
    st.session_state["active_case_id"] = payload["case_id"]
    st.session_state["active_payload"] = payload
    _save(payload, "new_case")
    st.rerun()


def _render_sidebar() -> None:
    st.sidebar.header("Cases")

    cases = list_cases(_paths())
    options = {c["case_id"]: _case_label(c) for c in cases if isinstance(c, dict) and "case_id" in c}
    active_case_id = st.session_state.get("active_case_id")

    if options:
        ids = list(options.keys())
        labels = list(options.values())
        default_index = ids.index(active_case_id) if active_case_id in ids else 0

        selected_label = st.sidebar.selectbox("Open case", labels, index=default_index, key="case_picker")
        selected_id = ids[labels.index(selected_label)]

        if selected_id != active_case_id:
            st.session_state["active_case_id"] = selected_id
            st.session_state["active_payload"] = read_draft(_paths(), selected_id)
            st.rerun()
    else:
        st.sidebar.info("No cases yet. Create one to start.")

    if st.sidebar.button("New case", key="new_case"):
        _new_case()

    st.sidebar.divider()
    st.sidebar.caption(f"Policy version {_policy().policy_version}")


def _widget_key(payload: Dict[str, Any], q: Question) -> str:
    """Keys are scoped to case and version.

    Streamlit session state wins over the value argument, so a key reused across
    cases would show, and then save, the previous case's answer.
    """
    return f"q_{payload['case_id']}_{payload.get('version', 1)}_{q.qid}"


def _render_question(q: Question, payload: Dict[str, Any]) -> Any:
    current = get_nested(payload, q.path)
    key = _widget_key(payload, q)
    rules = q.validation or {}
    help_text = q.help or None

    if q.input_type == "text":
        return st.text_input(q.text, value=str(current or ""), help=help_text, key=key)

    if q.input_type == "textarea":
        return st.text_area(q.text, value=str(current or ""), help=help_text, key=key)

    if q.input_type == "list_text":
        value = "\n".join(str(x) for x in current) if isinstance(current, list) else str(current or "")
        return st.text_area(q.text, value=value, help=help_text or "One per line.", key=key)

    if q.input_type == "single_select":
        opts = list(q.options or [])
        idx = opts.index(current) if current in opts else 0
        return st.selectbox(q.text, opts, index=idx, help=help_text, key=key)

    if q.input_type == "multi_select":
        opts = list(q.options or [])
        default = [v for v in (current or []) if v in opts] if isinstance(current, list) else []
        return st.multiselect(q.text, opts, default=default, help=help_text, key=key)

    if q.input_type in {"number", "slider"}:
        lo = int(rules.get("min", 0 if q.input_type == "number" else 1))
        hi = int(rules.get("max", 1_000_000 if q.input_type == "number" else 5))
        value = int(current) if current is not None else lo
        value = max(lo, min(hi, value))
        if q.input_type == "number":
            return st.number_input(q.text, min_value=lo, max_value=hi, value=value, step=1, help=help_text, key=key)
        return st.slider(q.text, min_value=lo, max_value=hi, value=value, help=help_text, key=key)

    if q.input_type == "scale":
        labels = q.option_labels or {}
        points = list(q.options or sorted(labels))
        value = int(current) if current in points else points[0]
        return st.select_slider(
            q.text,
            options=points,
            value=value,
            format_func=lambda v: f"{v} - {labels.get(v, '')}",
            help=help_text,
            key=key,
        )

    st.write("Unsupported question type.")
    return None


def _render_step(payload: Dict[str, Any], state: WizardStateEnum) -> None:
    questions = questions_for_state(_questions(), state)
    answers: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    for q in questions:
        answer = _render_question(q, payload)
        answers[q.path] = answer
        err = validate_answer(q, answer)
        if err:
            errors[q.path] = err
            st.caption(f":red[{q.text}: {err}]")

    col_back, col_save, col_next = st.columns(3)

    with col_back:
        if st.button("Back", key=f"back_{state.value}", disabled=state == WizardStateEnum.ANCHOR):
            for path, answer in answers.items():
                apply_answer(payload, path, answer)
            set_state(payload, prev_state(state))
            _save(payload, "back")
            st.rerun()

    with col_save:
        if st.button("Save", key=f"save_{state.value}"):
            for path, answer in answers.items():
                apply_answer(payload, path, answer)
            _save(payload, "save")
            st.success("Saved.")

    with col_next:
        if st.button("Next", key=f"next_{state.value}"):
            if errors:
                st.error("Fix the fields above before continuing.")
            else:
                for path, answer in answers.items():
                    apply_answer(payload, path, answer)
                set_state(payload, next_state(state))
                _save(payload, "next")
                st.rerun()


def _render_review(payload: Dict[str, Any]) -> None:
    st.write("Review the inputs, then evaluate. Evaluation locks this version.")

    incomplete = outstanding_steps(payload, _questions())
    if incomplete:
        st.error("Incomplete steps: " + ", ".join(incomplete))
        for step in incomplete:
            for path, message in step_errors(payload, _questions(), WizardStateEnum(step)).items():
                st.caption(f":red[{path}: {message}]")

    st.json(payload, expanded=False)

    col_back, col_finish = st.columns(2)

    with col_back:
        if st.button("Back", key="review_back"):
            set_state(payload, prev_state(WizardStateEnum.REVIEW))
            _save(payload, "back")
            st.rerun()

    with col_finish:
        if st.button("Evaluate and lock", key="finish", disabled=bool(incomplete)):
            draft, err = try_make_draft_model(payload)
            if draft is None:
                st.error("Validation failed:\n\n" + str(err))
                return

            compute_and_lock_snapshot(payload, _policy())
            case_id = str(payload["case_id"])
            version = int(payload.get("version", 1))

            _save(payload, "evaluate")
            write_snapshot(_paths(), case_id, version, payload["evaluation_snapshot"])
            write_decision(_paths(), case_id, version, payload["decision"])
            st.rerun()


def _render_end(payload: Dict[str, Any]) -> None:
    snapshot = payload.get("evaluation_snapshot") or {}
    decision = payload.get("decision") or {}

    st.success(f"Version {payload.get('version')} is locked.")

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Score", snapshot.get("overall_risk_score"))
    col_b.metric("Category", str(snapshot.get("risk_category", "")).upper())
    col_c.metric("Decision", str(decision.get("decision_type", "")))

    if snapshot.get("escalation_required"):
        st.warning("Escalation required. This cannot be accepted at risk owner level alone.")

    for message in (payload.get("feedback") or {}).get("messages", []):
        st.write(f"- {message}")

    st.caption(f"Inputs hash: {snapshot.get('inputs_hash', '')}")

    st.subheader("Override the recommendation")
    st.caption("The policy recommendation stands unless you record a reason.")

    recommended = str(snapshot.get("recommended_decision") or DecisionType.REDUCE.value)
    options = [d.value for d in DecisionType]
    index = options.index(recommended) if recommended in options else options.index(DecisionType.REDUCE.value)
    chosen = st.selectbox("Decision", options, index=index, key="override_decision")
    note = st.text_area("Reason for the override", key="override_note")

    if st.button("Record decision", key="record_decision"):
        follows = chosen == recommended
        if not follows and not note.strip():
            st.error("An override needs a documented reason.")
        else:
            record = DecisionRecord(
                decision_type=DecisionType(chosen),
                rationale=str(decision.get("rationale") or "Policy recommendation."),
                owner=str(get_nested(payload, "anchor.owner") or "unassigned"),
                follows_recommendation=follows,
                override_note=note.strip(),
            )
            payload["decision"] = record.model_dump(mode="json")
            write_decision(_paths(), str(payload["case_id"]), int(payload["version"]), payload["decision"])
            _save(payload, "decision_recorded" if follows else "decision_overridden")
            st.rerun()

    st.divider()
    if st.button("Revise as a new version", key="revise"):
        payload["version"] = int(payload.get("version", 1)) + 1
        payload["wizard"]["locked_at_end"] = False
        payload["evaluation_snapshot"] = None
        payload["decision"] = None
        payload["feedback"] = None
        set_state(payload, WizardStateEnum.ANCHOR)
        _save(payload, "new_version")
        st.rerun()


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    st.session_state.setdefault("paths", init_case_paths())
    st.session_state.setdefault("active_case_id", None)
    st.session_state.setdefault("active_payload", None)

    _render_sidebar()

    payload = st.session_state.get("active_payload")
    if payload is None and st.session_state.get("active_case_id"):
        payload = read_draft(_paths(), st.session_state["active_case_id"])
        st.session_state["active_payload"] = payload

    if payload is None:
        st.info("Create a new case to start.")
        return

    state = get_state(payload)
    st.subheader(f"Step: {state.value}")
    st.progress(_STEPS.index(state) / (len(_STEPS) - 1))

    if state == WizardStateEnum.END or is_locked(payload):
        _render_end(payload)
    elif state == WizardStateEnum.REVIEW:
        _render_review(payload)
    else:
        _render_step(payload, state)


_STEPS = list(WizardStateEnum)


if __name__ == "__main__":
    main()
