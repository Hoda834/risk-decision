from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json

import streamlit as st

from core.policy import load_policy
from core.questions import load_question_bank, resolve_options, option_labels, Question
from core.storage import StoragePaths, list_cases, write_case_meta, read_case_meta, write_version_files, read_version_draft, write_snapshot, write_decision, append_audit
from core.wizard import (
    WizardState,
    new_case_id,
    initial_payload,
    apply_answer,
    required_if_met,
    should_compute_snapshot,
    compute_and_lock_snapshot,
    make_draft_model,
    can_go_back,
    clone_to_new_version,
)

BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
POLICY_PATH = CONFIG_DIR / "policy_config.json"
QUESTIONS_PATH = CONFIG_DIR / "question_bank.json"

st.set_page_config(page_title="Risk Decision Framework", layout="wide")

policy = load_policy(POLICY_PATH)
questions = load_question_bank(QUESTIONS_PATH)
paths = StoragePaths(root=DATA_DIR)


def _init_session() -> None:
    if "wizard_state" not in st.session_state:
        st.session_state.wizard_state = None
    if "payload" not in st.session_state:
        st.session_state.payload = None


def _render_question(q: Question, payload: Dict[str, Any]) -> Any:
    q_opts = resolve_options(q, policy)
    labels = option_labels(q, policy)
    key = f"answer_{q.qid}"

    if q.input_type == "single_select":
        if q_opts is None:
            return st.text_input(q.text, key=key)
        if labels:
            display = [f"{o} - {labels.get(o, '')}".strip() for o in q_opts]
            selected = st.selectbox(q.text, options=list(range(len(q_opts))), format_func=lambda i: display[i], key=key)
            return q_opts[int(selected)]
        return st.selectbox(q.text, options=q_opts, key=key)

    if q.input_type == "multi_select":
        if q_opts is None:
            return []
        return st.multiselect(q.text, options=q_opts, key=key)

    if q.input_type == "text":
        return st.text_input(q.text, key=key)

    if q.input_type == "textarea":
        return st.text_area(q.text, key=key, height=140)

    if q.input_type == "list_text":
        raw = st.text_area(q.text, key=key, height=120, help="Enter one item per line.")
        items = [line.strip() for line in raw.splitlines() if line.strip()]
        return items

    return st.text_input(q.text, key=key)


def _current_question(state: WizardState) -> Question:
    return questions[state.current_index]


def _save_current(payload: Dict[str, Any]) -> None:
    draft = make_draft_model(payload)
    write_version_files(paths, draft)

    meta = {
        "case_id": draft.case_id,
        "created_at": payload.get("created_at"),
        "policy_version": draft.policy_version,
        "current_version": draft.version,
        "status": _status_from_payload(payload),
    }
    write_case_meta(paths, draft.case_id, meta)


def _status_from_payload(payload: Dict[str, Any]) -> str:
    if payload.get("decision") is not None:
        return "decided"
    if payload.get("evaluation_snapshot") is not None:
        return "evaluated"
    return "draft"


def _load_case(case_id: str) -> None:
    meta = read_case_meta(paths, case_id)
    version = int(meta.get("current_version", 1))
    draft = read_version_draft(paths, case_id, version)
    payload = draft.model_dump()
    snapshot_locked = payload.get("evaluation_snapshot") is not None
    state = WizardState(
        case_id=case_id,
        version=version,
        policy_version=str(payload.get("policy_version", policy.policy_version)),
        current_index=_index_from_payload(payload),
        snapshot_locked=bool(snapshot_locked),
    )
    st.session_state.payload = payload
    st.session_state.wizard_state = state
    append_audit(paths, case_id, "case_loaded", {"version": version})


def _index_from_payload(payload: Dict[str, Any]) -> int:
    if payload.get("decision") is not None:
        return len(questions) - 1
    if payload.get("evaluation_snapshot") is not None and payload.get("evaluation_feedback") is None:
        return _find_index("Q18")
    if payload.get("evaluation_snapshot") is not None and payload.get("evaluation_feedback") is not None and payload.get("decision") is None:
        return _find_index("Q20")
    return 0


def _find_index(qid: str) -> int:
    for i, q in enumerate(questions):
        if q.qid == qid:
            return i
    return 0


def _new_case() -> None:
    cid = new_case_id()
    version = 1
    payload = initial_payload(policy, cid, version)
    state = WizardState(
        case_id=cid,
        version=version,
        policy_version=policy.policy_version,
        current_index=0,
        snapshot_locked=False,
    )
    st.session_state.payload = payload
    st.session_state.wizard_state = state
    _save_current(payload)
    append_audit(paths, cid, "case_created", {"version": version})


def _render_snapshot(payload: Dict[str, Any]) -> None:
    snap = payload.get("evaluation_snapshot")
    if not snap:
        return
    left, right = st.columns(2)
    with left:
        st.metric("Score", f"{snap['score']}")
        st.write(f"Category: {snap['category']}")
    with right:
        st.write(f"Recommended decision: {snap['recommended_decision']}")
        st.write(f"Policy version: {snap['policy_version']}")
    st.divider()


def _render_case_sidebar() -> None:
    st.sidebar.header("Cases")
    cases = list_cases(paths)
    case_ids = [c.get("case_id") for c in cases if c.get("case_id")]
    selected = st.sidebar.selectbox("Open case", options=[""] + case_ids)
    if st.sidebar.button("New case", use_container_width=True):
        _new_case()
        st.rerun()
    if selected:
        if st.sidebar.button("Load selected", use_container_width=True):
            _load_case(selected)
            st.rerun()


_init_session()
_render_case_sidebar()

state: Optional[WizardState] = st.session_state.wizard_state
payload: Optional[Dict[str, Any]] = st.session_state.payload

if state is None or payload is None:
    st.title("Risk Decision Framework")
    st.write("Create or load a case from the sidebar.")
    st.stop()

st.title(f"Case {state.case_id}  Version {state.version}")

if payload.get("evaluation_snapshot") is not None:
    _render_snapshot(payload)

q = _current_question(state)

if q.qid == "Q18" and payload.get("evaluation_snapshot") is None:
    st.error("Snapshot missing. Continue the interview until Q17.")
    st.stop()

if q.qid == "Q19":
    required_now = required_if_met(payload, q)
else:
    required_now = q.required

answer = _render_question(q, payload)

col_a, col_b, col_c, col_d = st.columns(4)

with col_a:
    back_disabled = not can_go_back(state)
    if st.button("Back", disabled=back_disabled, use_container_width=True):
        state.current_index = max(0, state.current_index - 1)
        st.session_state.wizard_state = state
        append_audit(paths, state.case_id, "back", {"index": state.current_index, "qid": q.qid, "version": state.version})
        st.rerun()

with col_b:
    if st.button("Save", use_container_width=True):
        _save_current(payload)
        append_audit(paths, state.case_id, "saved", {"version": state.version, "qid": q.qid, "index": state.current_index})
        st.success("Saved.")

with col_c:
    if payload.get("evaluation_snapshot") is not None:
        if st.button("Edit by new version", use_container_width=True):
            new_payload, new_version = clone_to_new_version(payload, policy)
            state.version = new_version
            state.current_index = 0
            state.snapshot_locked = False
            st.session_state.payload = new_payload
            st.session_state.wizard_state = state
            _save_current(new_payload)
            append_audit(paths, state.case_id, "version_cloned", {"from_version": payload["version"], "to_version": new_version})
            st.rerun()

with col_d:
    if st.button("Next", use_container_width=True):
        if required_now:
            if q.input_type in {"text", "textarea"} and (not isinstance(answer, str) or not answer.strip()):
                st.error("This field is required.")
                st.stop()
            if q.input_type == "list_text" and (not isinstance(answer, list) or len(answer) < 1):
                st.error("At least one item is required.")
                st.stop()
            if q.input_type == "multi_select" and (not isinstance(answer, list) or len(answer) < 1):
                st.error("Select at least one option.")
                st.stop()

        apply_answer(payload, q, answer, policy)

        if should_compute_snapshot(q.qid):
            compute_and_lock_snapshot(payload, policy)
            state.snapshot_locked = True
            snap_json = json.dumps(payload["evaluation_snapshot"], ensure_ascii=False, indent=2)
            write_snapshot(paths, state.case_id, state.version, snap_json)
            append_audit(paths, state.case_id, "snapshot_created", {"version": state.version, "score": payload["evaluation_snapshot"]["score"]})

        if q.qid == "Q18":
            payload["evaluation_feedback"] = {"confirmed": (str(answer).lower() == "true"), "challenge_note": None}
            append_audit(paths, state.case_id, "evaluation_feedback_set", {"version": state.version, "confirmed": payload["evaluation_feedback"]["confirmed"]})

        if q.qid == "Q19":
            if payload.get("evaluation_feedback") is None:
                payload["evaluation_feedback"] = {"confirmed": False, "challenge_note": None}
            payload["evaluation_feedback"]["challenge_note"] = str(answer).strip()
            append_audit(paths, state.case_id, "evaluation_challenge_set", {"version": state.version})

        if q.qid == "Q20":
            decision_type = str(answer)
            rationale = st.session_state.get("decision_rationale", "")
            decision_owner = st.session_state.get("decision_owner", "")
            payload["decision"] = {"decision_type": decision_type, "rationale": rationale, "owner": decision_owner}
            write_decision(paths, state.case_id, state.version, json.dumps(payload["decision"], ensure_ascii=False, indent=2))
            append_audit(paths, state.case_id, "decision_set", {"version": state.version, "decision": decision_type})

        payload["updated_at"] = __import__("datetime").datetime.utcnow().isoformat()
        _save_current(payload)

        if state.current_index < len(questions) - 1:
            state.current_index += 1
        st.session_state.wizard_state = state
        st.session_state.payload = payload
        st.rerun()

if q.qid == "Q20":
    st.divider()
    st.subheader("Decision details")
    st.text_area("Decision rationale", key="decision_rationale", height=120)
    st.text_input("Decision owner", key="decision_owner")

if payload.get("decision") is not None:
    st.divider()
    st.subheader("Export")
    export_col1, export_col2 = st.columns(2)
    with export_col1:
        st.download_button(
            "Download current draft JSON",
            data=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"{state.case_id}_v{state.version:03d}_draft.json",
            mime="application/json",
            use_container_width=True,
        )
    with export_col2:
        st.download_button(
            "Download evaluation snapshot JSON",
            data=json.dumps(payload.get("evaluation_snapshot", {}), ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"{state.case_id}_v{state.version:03d}_snapshot.json",
            mime="application/json",
            use_container_width=True,
        )
