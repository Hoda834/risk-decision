from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from core.storage import CasePaths, init_case_paths, list_cases, read_draft, write_case_meta, write_draft, append_audit
from core.wizard import (
    WizardStateEnum,
    apply_answer,
    compute_and_lock_snapshot,
    get_state,
    initial_payload,
    next_state,
    prev_state,
    questions_for_state,
    set_state,
    try_make_draft_model,
    validate_answer_for_question,
)

APP_TITLE = "Risk Decision Wizard"


def _safe_case_label(case_item: Dict[str, Any]) -> str:
    case_id = case_item.get("case_id", "unknown")
    name = ""
    anchor = case_item.get("anchor") or {}
    if isinstance(anchor, dict):
        name = (anchor.get("name") or "").strip()
    if not name:
        name = (case_item.get("case_name") or "").strip()
    if not name:
        name = "Untitled case"
    return f"{name} ({case_id})"


def _load_case(case_id: str) -> Dict[str, Any]:
    paths: CasePaths = st.session_state["paths"]
    payload = read_draft(paths, case_id)
    if not isinstance(payload, dict):
        raise ValueError("Draft payload is not a dictionary.")
    return payload


def _bump_version(payload: Dict[str, Any]) -> int:
    v = int(payload.get("version", 1))
    v += 1
    payload["version"] = v
    return v


def _save_current(payload: Dict[str, Any], reason: str) -> None:
    paths: CasePaths = st.session_state["paths"]
    case_id = str(payload["case_id"])
    version = int(payload.get("version", 1))

    write_draft(paths, case_id, version, payload)

    anchor = payload.get("anchor") if isinstance(payload.get("anchor"), dict) else {}
    meta = {
        "case_name": (anchor.get("name") or "Untitled case"),
        "anchor": {"name": (anchor.get("name") or "Untitled case")},
        "updated_at": None,
        "latest_version": version,
    }
    write_case_meta(paths, case_id, meta)
    append_audit(paths, case_id, {"action": reason, "version": version})


def _new_case() -> None:
    payload = initial_payload()
    st.session_state["active_case_id"] = payload["case_id"]
    st.session_state["active_payload"] = payload
    _save_current(payload, "new_case")
    st.rerun()


def _render_case_sidebar() -> None:
    st.sidebar.header("Cases")

    cases = list_cases(st.session_state["paths"])
    options = {c["case_id"]: _safe_case_label(c) for c in cases if isinstance(c, dict) and "case_id" in c}

    active_case_id = st.session_state.get("active_case_id")

    if options:
        labels = list(options.values())
        ids = list(options.keys())
        default_index = ids.index(active_case_id) if active_case_id in ids else 0

        selected_label = st.sidebar.selectbox("Open case", labels, index=default_index)
        selected_id = ids[labels.index(selected_label)]

        if selected_id != active_case_id:
            st.session_state["active_case_id"] = selected_id
            st.session_state["active_payload"] = _load_case(selected_id)
            st.rerun()
    else:
        st.sidebar.info("No cases found. Create a new case to start.")

    if st.sidebar.button("New case"):
        _new_case()

    last_err = st.session_state.get("last_validation_error")
    if last_err:
        st.sidebar.warning("Final validation failed. Keep editing, then try Finish again.")


def _render_question(q, payload: Dict[str, Any]) -> Any:
    parts = q.key.split(".")
    cur: Any = payload
    for p in parts[:-1]:
        cur = cur.get(p, {}) if isinstance(cur, dict) else {}
    current_value = cur.get(parts[-1], None) if isinstance(cur, dict) else None

    if q.kind == "text":
        return st.text_input(q.label, value=str(current_value or ""), help=q.help)

    if q.kind == "textarea":
        if isinstance(current_value, list):
            current_value = "\n".join([str(x) for x in current_value])
        return st.text_area(q.label, value=str(current_value or ""), help=q.help)

    if q.kind == "selectbox":
        opts = q.options or []
        idx = opts.index(current_value) if current_value in opts else 0
        return st.selectbox(q.label, opts, index=idx, help=q.help)

    if q.kind == "multiselect":
        opts = q.options or []
        default = [v for v in (current_value or []) if v in opts] if isinstance(current_value, list) else []
        return st.multiselect(q.label, opts, default=default, help=q.help)

    if q.kind == "slider":
        v = int(current_value) if current_value is not None else q.slider_min
        return st.slider(q.label, min_value=q.slider_min, max_value=q.slider_max, value=v, step=q.slider_step, help=q.help)

    if q.kind == "number":
        v = int(current_value) if current_value is not None else 0
        return st.number_input(q.label, value=v, step=1, help=q.help)

    st.write("Unsupported question type.")
    return None


def _render_current_page(payload: Dict[str, Any]) -> None:
    state = get_state(payload)
    st.subheader(f"Step: {state.value}")

    if state == WizardStateEnum.REVIEW:
        st.write("Review your inputs, then click Finish.")
        st.json(payload)

        if st.button("Finish"):
            payload = compute_and_lock_snapshot(payload)
            draft, err = try_make_draft_model(payload)

            if draft is None:
                st.session_state["last_validation_error"] = err
                st.error("Validation failed. Fix the issues and try again.")
            else:
                st.session_state["last_validation_error"] = None
                _bump_version(payload)
                _save_current(payload, "finish")
                st.success("Saved and validated.")
                st.session_state["active_payload"] = payload
                st.rerun()
        return

    if state == WizardStateEnum.END:
        st.success("This case is finalised.")
        st.json(payload.get("evaluation_snapshot"))
        st.json(payload.get("decision"))

        if st.button("Edit (new version)"):
            set_state(payload, WizardStateEnum.ANCHOR)
            if isinstance(payload.get("wizard"), dict):
                payload["wizard"]["locked_at_end"] = False
            _bump_version(payload)
            _save_current(payload, "edit_from_end")
            st.session_state["active_payload"] = payload
            st.rerun()
        return

    questions = questions_for_state(state)
    if not questions:
        st.info("No questions for this step.")
        return

    answers: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    for q in questions:
        ans = _render_question(q, payload)
        answers[q.key] = ans
        err = validate_answer_for_question(q, ans)
        if err:
            errors[q.key] = err

    if errors:
        st.error("Fix the highlighted fields before continuing.")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Back"):
            prev = prev_state(state)
            set_state(payload, prev)
            _bump_version(payload)
            _save_current(payload, "back")
            st.session_state["active_payload"] = payload
            st.rerun()

    with col2:
        if st.button("Save"):
            if errors:
                st.error("Fix validation errors before saving.")
            else:
                for k, a in answers.items():
                    payload = apply_answer(payload, k, a)
                _bump_version(payload)
                _save_current(payload, "save")
                st.session_state["active_payload"] = payload
                st.success("Saved.")

    with col3:
        if st.button("Next"):
            if errors:
                st.error("Fix validation errors before continuing.")
            else:
                for k, a in answers.items():
                    payload = apply_answer(payload, k, a)
                nxt = next_state(state)
                set_state(payload, nxt)
                _bump_version(payload)
                _save_current(payload, "next")
                st.session_state["active_payload"] = payload
                st.rerun()


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    if "paths" not in st.session_state:
        st.session_state["paths"] = init_case_paths(".")
    if "active_case_id" not in st.session_state:
        st.session_state["active_case_id"] = None
    if "active_payload" not in st.session_state:
        st.session_state["active_payload"] = None
    if "last_validation_error" not in st.session_state:
        st.session_state["last_validation_error"] = None

    _render_case_sidebar()

    active_payload = st.session_state.get("active_payload")
    active_case_id = st.session_state.get("active_case_id")

    if active_payload is None and active_case_id:
        st.session_state["active_payload"] = _load_case(active_case_id)
        active_payload = st.session_state["active_payload"]

    if active_payload is None:
        st.info("Create a new case to start.")
        return

    _render_current_page(active_payload)


if __name__ == "__main__":
    main()
