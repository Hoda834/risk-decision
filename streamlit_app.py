from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import streamlit as st


APP_TITLE = "Risk Decision Wizard"


# -------- Imports (supports both layouts: core/* or flat files) --------
try:
    # Preferred: core package layout
    from core.storage import CasePaths, init_case_paths, read_draft, write_draft, list_cases  # type: ignore
    from core.wizard import (  # type: ignore
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
except ModuleNotFoundError:
    # Fallback: flat layout
    from storage import CasePaths, init_case_paths, read_draft, write_draft, list_cases  # type: ignore
    from wizard import (  # type: ignore
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


# -------- Helpers --------
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


def _coerce_state(payload: Dict[str, Any]) -> WizardStateEnum:
    wiz = payload.get("wizard") or {}
    raw = wiz.get("state")
    if not raw:
        return WizardStateEnum.DRAFT
    try:
        return WizardStateEnum(raw)
    except Exception:
        return WizardStateEnum.DRAFT


def _compute_next_state(cur: WizardStateEnum, payload: Dict[str, Any]) -> WizardStateEnum:
    # supports next_state(state) or next_state(state, payload)
    try:
        return next_state(cur)  # type: ignore[misc]
    except TypeError:
        return next_state(cur, payload)  # type: ignore[misc]


def _compute_prev_state(payload: Dict[str, Any]) -> WizardStateEnum:
    # supports step_back(payload) or step_back(payload, state)
    try:
        return step_back(payload)  # type: ignore[misc]
    except TypeError:
        cur = _coerce_state(payload)
        return step_back(payload, cur)  # type: ignore[misc]


def _json_dumps_safe(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)


def _validate_final(payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    draft, err = try_make_draft_model(payload)
    if draft is None:
        return None, str(err) if err is not None else "Final validation failed."
    data = draft.model_dump() if hasattr(draft, "model_dump") else draft
    if not isinstance(data, dict):
        return None, "Validated draft is not a dictionary."
    return data, None


def _save_current(payload: Dict[str, Any]) -> None:
    paths: CasePaths = st.session_state["paths"]
    case_id = payload.get("case_id")
    if not case_id:
        raise ValueError("Payload is missing case_id.")

    version = int(payload.get("version", 1))
    state = _coerce_state(payload)

    payload_to_write: Dict[str, Any] = payload
    final_err: Optional[str] = None

    # If state is END, attempt final validation but never crash the app.
    if state == WizardStateEnum.END:
        validated, err = _validate_final(payload)
        if validated is not None:
            payload_to_write = validated
            st.session_state["last_validation_error"] = None
        else:
            final_err = err
            st.session_state["last_validation_error"] = final_err
            payload_to_write = dict(payload)
            payload_to_write["_final_validation_error"] = final_err

    content = _json_dumps_safe(payload_to_write)
    write_draft(paths, case_id, version, content)


def _new_case() -> None:
    payload = initial_payload()

    # Safety: if something upstream sets END by mistake, force to DRAFT.
    try:
        cur = _coerce_state(payload)
        if cur == WizardStateEnum.END:
            set_state(payload, WizardStateEnum.DRAFT)
    except Exception:
        pass

    _save_current(payload)
    st.session_state["active_case_id"] = payload["case_id"]
    st.session_state["active_payload"] = payload
    st.rerun()


def _load_case(case_id: str) -> Dict[str, Any]:
    paths: CasePaths = st.session_state["paths"]
    payload = read_draft(paths, case_id)
    if not isinstance(payload, dict):
        raise ValueError("Draft payload is not a dictionary.")
    return payload


def _render_case_sidebar() -> None:
    st.sidebar.header("Cases")

    try:
        cases = list_cases(st.session_state["paths"])
    except Exception as e:
        st.sidebar.error(f"Failed to load cases: {e}")
        cases = []

    case_map: Dict[str, Dict[str, Any]] = {}
    for c in cases:
        if isinstance(c, dict) and "case_id" in c:
            case_map[str(c["case_id"])] = c

    active_case_id = st.session_state.get("active_case_id")

    if case_map:
        ids = sorted(case_map.keys())
        default_index = ids.index(active_case_id) if active_case_id in ids else 0

        selected_id = st.sidebar.selectbox(
            "Open case",
            options=ids,
            index=default_index,
            format_func=lambda cid: _safe_case_label(case_map.get(cid, {"case_id": cid})),
        )

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
        st.sidebar.warning("Final validation failed. Keep editing. It will pass once required fields are completed.")


def _get_value_by_key(payload: Dict[str, Any], dotted_key: str) -> Any:
    parts = dotted_key.split(".")
    cur: Any = payload
    for p in parts[:-1]:
        if isinstance(cur, dict):
            cur = cur.get(p, {})
        else:
            return None
    if isinstance(cur, dict):
        return cur.get(parts[-1], None)
    return None


def _render_question(q, payload: Dict[str, Any], widget_key: str) -> Any:
    current_value = _get_value_by_key(payload, q.key)

    if q.kind == "text":
        return st.text_input(q.label, value=(current_value or ""), help=q.help, key=widget_key)

    if q.kind == "textarea":
        return st.text_area(q.label, value=(current_value or ""), help=q.help, key=widget_key)

    if q.kind == "selectbox":
        opts = q.options or []
        if not opts:
            return st.text_input(q.label, value=(current_value or ""), help=q.help, key=widget_key)

        idx = opts.index(current_value) if current_value in opts else 0
        return st.selectbox(q.label, opts, index=idx, help=q.help, key=widget_key)

    if q.kind == "multiselect":
        opts = q.options or []
        if isinstance(current_value, list):
            default = [v for v in current_value if v in opts]
        else:
            default = []
        return st.multiselect(q.label, opts, default=default, help=q.help, key=widget_key)

    if q.kind == "slider":
        v = current_value if isinstance(current_value, (int, float)) else q.slider_min
        return st.slider(
            q.label,
            min_value=q.slider_min,
            max_value=q.slider_max,
            value=v,
            step=q.slider_step,
            help=q.help,
            key=widget_key,
        )

    st.info(f"Unsupported question type: {q.kind}")
    return None


def _apply_answers(payload: Dict[str, Any], answers: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in answers.items():
        payload = apply_answer(payload, k, v)
    return payload


def _finalise_case(payload: Dict[str, Any]) -> None:
    validated, err = _validate_final(payload)
    if validated is None:
        st.session_state["last_validation_error"] = err
        st.error(err or "Final validation failed.")
        _save_current(payload)  # saves draft with _final_validation_error
        return

    set_state(payload, WizardStateEnum.END)
    st.session_state["last_validation_error"] = None

    # Save the validated payload as the final stored content
    paths: CasePaths = st.session_state["paths"]
    case_id = payload["case_id"]
    version = int(payload.get("version", 1))
    content = _json_dumps_safe(validated)
    write_draft(paths, case_id, version, content)

    st.session_state["active_payload"] = payload
    st.success("Finalised successfully.")
    st.rerun()


def _render_current_page(payload: Dict[str, Any]) -> None:
    state = _coerce_state(payload)
    st.subheader(f"Step: {state.value}")

    questions = questions_for_state(state)

    if not questions:
        st.info("No questions for this step.")
        col_a, col_b = st.columns([1, 1])
        with col_a:
            if st.button("Back"):
                prev = _compute_prev_state(payload)
                set_state(payload, prev)
                _save_current(payload)
                st.session_state["active_payload"] = payload
                st.rerun()
        with col_b:
            if st.button("Finish"):
                _finalise_case(payload)
        return

    case_id = payload.get("case_id", "case")
    form_key = f"form_{case_id}_{state.value}"

    with st.form(key=form_key):
        answers: Dict[str, Any] = {}
        errors: Dict[str, str] = {}

        for i, q in enumerate(questions):
            widget_key = f"{case_id}_{state.value}_{i}_{q.key}"
            ans = _render_question(q, payload, widget_key=widget_key)
            answers[q.key] = ans

            err = validate_answer_for_question(q, ans)
            if err:
                errors[q.key] = err
                st.error(err)

        col1, col2, col3, col4 = st.columns(4)

        back_pressed = col1.form_submit_button("Back")
        save_pressed = col2.form_submit_button("Save")
        next_pressed = col3.form_submit_button("Next")
        finish_pressed = col4.form_submit_button("Finish")

    if back_pressed:
        prev = _compute_prev_state(payload)
        set_state(payload, prev)
        _save_current(payload)
        st.session_state["active_payload"] = payload
        st.rerun()

    if save_pressed:
        if errors:
            st.error("Fix the validation errors before saving.")
        else:
            payload = _apply_answers(payload, answers)
            _save_current(payload)
            st.session_state["active_payload"] = payload
            st.success("Saved.")

    if next_pressed:
        if errors:
            st.error("Fix the validation errors before continuing.")
        else:
            payload = _apply_answers(payload, answers)
            nxt = _compute_next_state(state, payload)
            set_state(payload, nxt)
            _save_current(payload)
            st.session_state["active_payload"] = payload
            st.rerun()

    if finish_pressed:
        if errors:
            st.error("Fix the validation errors before finishing.")
        else:
            payload = _apply_answers(payload, answers)
            _finalise_case(payload)


def _init_paths() -> CasePaths:
    # Use repo root if possible, otherwise current working directory.
    try:
        here = Path(__file__).resolve().parent
        return init_case_paths(str(here))
    except Exception:
        return init_case_paths(".")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    if "paths" not in st.session_state:
        st.session_state["paths"] = _init_paths()
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
