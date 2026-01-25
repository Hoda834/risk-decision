from __future__ import annotations

import json
from typing import Any, Dict

import streamlit as st

from core.storage import CasePaths, init_case_paths, read_draft, write_draft, list_cases
from core.wizard import (
    WizardStateEnum,
    initial_payload,
    apply_answer,
    validate_answer_for_question,
    next_state,
    step_back,
    questions_for_state,
    set_state,
    try_make_draft_model,
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


def _save_current(payload: Dict[str, Any]) -> None:
    paths: CasePaths = st.session_state["paths"]
    case_id = payload["case_id"]
    version = int(payload.get("version", 1))

    state_str = (payload.get("wizard") or {}).get("state", WizardStateEnum.ANCHOR.value)
    payload_to_write: Dict[str, Any] = payload

    if state_str == WizardStateEnum.END.value:
        draft, err = try_make_draft_model(payload)
        if draft is not None:
            payload_to_write = draft.model_dump()
            payload_to_write["wizard"] = payload.get("wizard", {"state": WizardStateEnum.END.value})
            st.session_state["last_validation_error"] = None
        else:
            st.session_state["last_validation_error"] = err

    content = json.dumps(payload_to_write, indent=2, ensure_ascii=False)
    write_draft(paths, case_id, version, content)


def _new_case() -> None:
    payload = initial_payload()
    _save_current(payload)
    st.session_state["active_case_id"] = payload["case_id"]
    st.session_state["active_payload"] = payload
    st.rerun()


def _load_case(case_id: str) -> Dict[str, Any]:
    paths: CasePaths = st.session_state["paths"]
    payload = read_draft(paths, case_id)
    if not isinstance(payload, dict):
        raise ValueError("Draft payload is not a dictionary.")
    payload.setdefault("wizard", {"state": WizardStateEnum.ANCHOR.value})
    payload.setdefault("case_id", case_id)
    payload.setdefault("version", 1)
    return payload


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
        st.sidebar.warning("Final validation failed. Finish will pass once required fields are completed.")


def _render_question(q, payload: Dict[str, Any]) -> Any:
    parts = q.key.split(".")
    cur: Any = payload
    for p in parts[:-1]:
        cur = cur.get(p, {}) if isinstance(cur, dict) else {}
    current_value = cur.get(parts[-1], None) if isinstance(cur, dict) else None

    if q.kind == "text":
        return st.text_input(q.label, value=(current_value or ""), help=q.help)

    if q.kind == "textarea":
        return st.text_area(q.label, value=(current_value or ""), help=q.help)

    if q.kind == "textarea_list":
        if isinstance(current_value, list):
            default_text = "\n".join(str(x) for x in current_value)
        else:
            default_text = ""
        return st.text_area(q.label, value=default_text, help=q.help)

    if q.kind == "selectbox":
        opts = list(q.options or [])
        idx = opts.index(current_value) if current_value in opts else 0
        return st.selectbox(q.label, opts, index=idx, help=q.help)

    if q.kind == "multiselect":
        opts = list(q.options or [])
        if isinstance(current_value, (list, set, tuple)):
            default = [v for v in list(current_value) if v in opts]
        else:
            default = []
        return st.multiselect(q.label, opts, default=default, help=q.help)

    if q.kind == "slider":
        v = int(current_value) if current_value is not None else q.slider_min
        return st.slider(
            q.label,
            min_value=q.slider_min,
            max_value=q.slider_max,
            value=v,
            step=q.slider_step,
            help=q.help,
        )

    st.write("Unsupported question type.")
    return None


def _render_current_page(payload: Dict[str, Any]) -> None:
    wiz = payload.get("wizard") or {}
    state = WizardStateEnum(wiz.get("state", WizardStateEnum.ANCHOR.value))

    st.subheader(f"Step: {state.value}")

    if state == WizardStateEnum.REVIEW:
        st.write("Review your draft below. Use Finish to validate.")
        st.json(payload)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Back"):
                prev = step_back(payload)
                set_state(payload, prev)
                _save_current(payload)
                st.session_state["active_payload"] = payload
                st.rerun()
        with col2:
            if st.button("Finish"):
                set_state(payload, WizardStateEnum.END)
                _save_current(payload)
                st.session_state["active_payload"] = payload
                st.rerun()
        return

    if state == WizardStateEnum.END:
        draft, err = try_make_draft_model(payload)
        if draft is None:
            st.error("Final validation failed.")
            st.text(err or "Unknown validation error.")
            if st.button("Back to review"):
                set_state(payload, WizardStateEnum.REVIEW)
                _save_current(payload)
                st.session_state["active_payload"] = payload
                st.rerun()
            return

        st.success("Validated successfully.")
        st.write("Final draft:")
        st.json(draft.model_dump())
        return

    questions = questions_for_state(state)
    if not questions:
        st.info("No questions for this step.")
        if st.button("Next"):
            nxt = next_state(state)
            set_state(payload, nxt)
            _save_current(payload)
            st.session_state["active_payload"] = payload
            st.rerun()
        return

    answers: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    for q in questions:
        ans = _render_question(q, payload)
        answers[q.key] = ans
        err = validate_answer_for_question(q, ans)
        if err:
            errors[q.key] = err
            st.error(f"{q.label}: {err}")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Back"):
            prev = step_back(payload)
            set_state(payload, prev)
            _save_current(payload)
            st.session_state["active_payload"] = payload
            st.rerun()

    with col2:
        if st.button("Save"):
            if errors:
                st.error("Fix the validation errors before saving.")
            else:
                for k, v in answers.items():
                    payload = apply_answer(payload, k, v)
                _save_current(payload)
                st.session_state["active_payload"] = payload
                st.success("Saved.")

    with col3:
        if st.button("Next"):
            if errors:
                st.error("Fix the validation errors before continuing.")
            else:
                for k, v in answers.items():
                    payload = apply_answer(payload, k, v)
                nxt = next_state(state)
                set_state(payload, nxt)
                _save_current(payload)
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
