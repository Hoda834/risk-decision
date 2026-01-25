from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WizardState:
    case_id: str
    version: int
    policy_version: str
    current_index: int = 0
    snapshot_locked: bool = False
    decision_locked: bool = False


@dataclass
class DraftModel:
    case_id: str
    version: int
    policy_version: str
    payload: Dict[str, Any]

    def model_dump(self) -> Dict[str, Any]:
        return dict(self.payload)


def new_case_id() -> str:
    return uuid.uuid4().hex[:10]


def initial_payload(policy: Any, case_id: str, version: int = 1) -> Dict[str, Any]:
    now = _utc_iso()
    policy_version = getattr(policy, "policy_version", "unknown")
    return {
        "case_id": case_id,
        "version": int(version),
        "policy_version": str(policy_version),
        "created_at": now,
        "updated_at": now,
        "answers": {},
        "progress": {"answered": 0, "total": 0, "percent": 0.0, "snapshot_locked": False, "decision_locked": False},
        "evaluation_snapshot": None,
        "decision": None,
        "notes": [],
    }


def latest_version_id(meta: Optional[Dict[str, Any]], payload: Optional[Dict[str, Any]]) -> int:
    mv = 0
    if meta and meta.get("current_version") is not None:
        try:
            mv = int(meta["current_version"])
        except Exception:
            mv = 0
    pv = 0
    if payload and payload.get("version") is not None:
        try:
            pv = int(payload["version"])
        except Exception:
            pv = 0
    return max(mv, pv, 1)


def make_draft_model(payload: Dict[str, Any]) -> DraftModel:
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")

    case_id = str(payload.get("case_id") or "").strip()
    if not case_id:
        case_id = new_case_id()
        payload["case_id"] = case_id

    try:
        version = int(payload.get("version") or 1)
    except Exception:
        version = 1
        payload["version"] = 1

    policy_version = str(payload.get("policy_version") or "unknown")
    payload.setdefault("policy_version", policy_version)

    payload.setdefault("created_at", _utc_iso())
    payload["updated_at"] = _utc_iso()
    payload.setdefault("answers", {})
    payload.setdefault("notes", [])

    return DraftModel(case_id=case_id, version=version, policy_version=policy_version, payload=payload)


def compute_progress(draft: DraftModel, policy: Any, questions: List[Any]) -> Dict[str, Any]:
    payload = draft.payload or {}
    answers = payload.get("answers") or {}
    if not isinstance(answers, dict):
        answers = {}

    total = len(questions) if questions else 0
    answered = 0

    for q in questions or []:
        qid = getattr(q, "qid", None) or getattr(q, "id", None)
        if not qid:
            continue
        val = answers.get(str(qid))
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        if isinstance(val, list) and len(val) == 0:
            continue
        answered += 1

    percent = (answered / total) * 100.0 if total else 0.0
    snapshot_locked = bool(payload.get("evaluation_snapshot"))
    decision_locked = bool(payload.get("decision"))

    return {
        "answered": answered,
        "total": total,
        "percent": round(percent, 1),
        "snapshot_locked": snapshot_locked,
        "decision_locked": decision_locked,
    }


def load_question_bank(policy: Any) -> List[Any]:
    from core.questions import load_question_bank as _load
    return _load(policy)


def should_compute_snapshot(qid: str) -> bool:
    from core.questions import should_compute_snapshot as _should
    return _should(qid)


def required_if_met(payload: Dict[str, Any], q: Any) -> bool:
    rule = getattr(q, "required_if", None)
    if not rule:
        return bool(getattr(q, "required", False))

    answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
    if isinstance(rule, dict):
        for dep_qid, dep_val in rule.items():
            actual = answers.get(str(dep_qid))
            if isinstance(dep_val, list):
                if actual in dep_val:
                    return True
            else:
                if actual == dep_val:
                    return True
        return False

    return bool(getattr(q, "required", False))


def can_go_back(state: WizardState) -> bool:
    return state.current_index > 0


def _set_by_path(payload: Dict[str, Any], path: Any, value: Any) -> None:
    if isinstance(path, str):
        keys = [k for k in path.split(".") if k]
    elif isinstance(path, (list, tuple)):
        keys = [str(k) for k in path if str(k)]
    else:
        keys = []

    if not keys:
        return

    cur: Any = payload
    for k in keys[:-1]:
        if not isinstance(cur, dict):
            return
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    if isinstance(cur, dict):
        cur[keys[-1]] = value


def apply_answer(payload: Dict[str, Any], q: Any, answer: Any, policy: Any) -> Dict[str, Any]:
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        answers = {}

    qid = getattr(q, "qid", None) or getattr(q, "id", None)
    if qid:
        answers[str(qid)] = answer
    payload["answers"] = answers

    path = getattr(q, "path", None) or getattr(q, "target_path", None)
    if path:
        _set_by_path(payload, path, answer)

    payload["updated_at"] = _utc_iso()
    return payload


def compute_and_lock_snapshot(payload: Dict[str, Any], policy: Any) -> Tuple[Dict[str, Any], str]:
    snapshot: Dict[str, Any]
    try:
        from core.engine import compute_snapshot  # اگر وجود داشت
        snapshot = compute_snapshot(payload=payload, policy=policy)
    except Exception:
        answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
        snapshot = {
            "computed_at": _utc_iso(),
            "policy_version": payload.get("policy_version", "unknown"),
            "answered_count": len(answers),
            "score": len(answers),
            "category": "draft",
            "recommended_decision": "continue",
        }

    payload["evaluation_snapshot"] = snapshot
    payload["updated_at"] = _utc_iso()
    return snapshot, json.dumps(snapshot, ensure_ascii=False, indent=2)


def clone_to_new_version(payload: Dict[str, Any], policy: Any) -> Tuple[Dict[str, Any], int]:
    current_version = int(payload.get("version") or 1)
    new_version = current_version + 1
    new_payload = json.loads(json.dumps(payload))
    new_payload["version"] = new_version
    new_payload["evaluation_snapshot"] = None
    new_payload["decision"] = None
    new_payload["updated_at"] = _utc_iso()
    return new_payload, new_version
