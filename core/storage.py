from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


@dataclass(frozen=True)
class StoragePaths:
    root: Path

    @property
    def cases_dir(self) -> Path:
        return self.root / "cases"

    def case_dir(self, case_id: str) -> Path:
        return self.cases_dir / case_id

    def meta_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "meta.json"

    def draft_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "draft.json"

    def versions_dir(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "versions"

    def version_dir(self, case_id: str, version: int) -> Path:
        return self.versions_dir(case_id) / f"v{int(version):04d}"

    def version_draft_path(self, case_id: str, version: int) -> Path:
        return self.version_dir(case_id, version) / "draft.json"

    def snapshot_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "snapshot.json"

    def decision_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "decision.json"

    def version_snapshot_path(self, case_id: str, version: int) -> Path:
        return self.version_dir(case_id, version) / "snapshot.json"

    def version_decision_path(self, case_id: str, version: int) -> Path:
        return self.version_dir(case_id, version) / "decision.json"

    def audit_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "audit.jsonl"


def list_case_ids(paths: StoragePaths) -> List[str]:
    if not paths.cases_dir.exists():
        return []
    ids = [p.name for p in paths.cases_dir.iterdir() if p.is_dir()]
    ids.sort()
    return ids


def read_case_meta(paths: StoragePaths, case_id: str) -> Optional[Dict[str, Any]]:
    obj = _read_json(paths.meta_path(case_id))
    return obj if isinstance(obj, dict) else None


def write_case_meta(paths: StoragePaths, case_id: str, meta_updates: Dict[str, Any]) -> Dict[str, Any]:
    existing = read_case_meta(paths, case_id) or {}
    merged = dict(existing)
    merged.update(meta_updates or {})
    merged.setdefault("case_id", case_id)
    merged.setdefault("created_at", existing.get("created_at") or _utc_iso())
    merged["updated_at"] = _utc_iso()
    _write_json_atomic(paths.meta_path(case_id), merged)
    return merged


def write_version_files(paths: StoragePaths, draft: Any) -> None:
    if hasattr(draft, "model_dump") and callable(getattr(draft, "model_dump")):
        payload = draft.model_dump()
        case_id = getattr(draft, "case_id", None) or payload.get("case_id")
        version = getattr(draft, "version", None) or payload.get("version")
    else:
        payload = dict(draft)
        case_id = payload.get("case_id")
        version = payload.get("version")

    if not case_id:
        raise ValueError("case_id missing in draft payload")
    if version is None:
        raise ValueError("version missing in draft payload")

    case_id = str(case_id)
    version = int(version)

    payload = dict(payload)
    payload.setdefault("case_id", case_id)
    payload["version"] = version
    payload.setdefault("updated_at", _utc_iso())

    _write_json_atomic(paths.draft_path(case_id), payload)
    _write_json_atomic(paths.version_draft_path(case_id, version), payload)

    write_case_meta(paths, case_id, {"current_version": version, "policy_version": payload.get("policy_version")})


def read_version_draft(paths: StoragePaths, case_id: str, version: int) -> Optional[Dict[str, Any]]:
    obj = _read_json(paths.version_draft_path(case_id, int(version)))
    if isinstance(obj, dict):
        return obj
    obj2 = _read_json(paths.draft_path(case_id))
    return obj2 if isinstance(obj2, dict) else None


def write_snapshot(paths: StoragePaths, case_id: str, version: int, snapshot_json: str) -> None:
    try:
        snapshot = json.loads(snapshot_json)
    except Exception:
        snapshot = {"raw": snapshot_json}

    _write_json_atomic(paths.snapshot_path(case_id), snapshot)
    _write_json_atomic(paths.version_snapshot_path(case_id, int(version)), snapshot)


def write_decision(paths: StoragePaths, case_id: str, version: int, decision_json: str) -> None:
    try:
        decision = json.loads(decision_json)
    except Exception:
        decision = {"raw": decision_json}

    _write_json_atomic(paths.decision_path(case_id), decision)
    _write_json_atomic(paths.version_decision_path(case_id, int(version)), decision)


def append_audit(paths: StoragePaths, case_id: str, event: str, details: Optional[Dict[str, Any]] = None) -> None:
    record: Dict[str, Any] = {"ts": _utc_iso(), "event": str(event)}
    if details:
        record["details"] = details
    _append_jsonl(paths.audit_path(case_id), record)


def delete_case(paths: StoragePaths, case_id: str) -> None:
    shutil.rmtree(paths.case_dir(case_id), ignore_errors=True)


def list_cases(paths: StoragePaths) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for cid in list_case_ids(paths):
        meta = read_case_meta(paths, cid) or {}
        current_version = meta.get("current_version")
        if current_version is None:
            current_version = 1
        cases.append(
            {
                "case_id": cid,
                "current_version": int(current_version),
                "updated_at": meta.get("updated_at"),
                "policy_version": meta.get("policy_version"),
            }
        )
    cases.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return cases
