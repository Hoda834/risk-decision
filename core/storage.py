from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.models import RiskCaseDraft


@dataclass(frozen=True)
class StoragePaths:
    root: Path

    def case_dir(self, case_id: str) -> Path:
        return self.root / "cases" / case_id

    def versions_dir(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "versions"

    def meta_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "case_meta.json"

    def audit_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "audit_log.jsonl"

    def version_prefix(self, version: int) -> str:
        return f"v{version:03d}"

    def draft_path(self, case_id: str, version: int) -> Path:
        return self.versions_dir(case_id) / f"{self.version_prefix(version)}_draft.json"

    def snapshot_path(self, case_id: str, version: int) -> Path:
        return self.versions_dir(case_id) / f"{self.version_prefix(version)}_evaluation_snapshot.json"

    def decision_path(self, case_id: str, version: int) -> Path:
        return self.versions_dir(case_id) / f"{self.version_prefix(version)}_decision.json"


def ensure_case_structure(paths: StoragePaths, case_id: str) -> None:
    cdir = paths.case_dir(case_id)
    vdir = paths.versions_dir(case_id)
    cdir.mkdir(parents=True, exist_ok=True)
    vdir.mkdir(parents=True, exist_ok=True)
    if not paths.audit_path(case_id).exists():
        paths.audit_path(case_id).write_text("", encoding="utf-8")


def list_cases(paths: StoragePaths) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    base = paths.root / "cases"
    if not base.exists():
        return out
    for cdir in sorted([p for p in base.iterdir() if p.is_dir()]):
        meta = paths.meta_path(cdir.name)
        if meta.exists():
            try:
                out.append(json.loads(meta.read_text(encoding="utf-8")))
            except Exception:
                continue
    return out


def read_case_meta(paths: StoragePaths, case_id: str) -> Dict[str, Any]:
    meta = paths.meta_path(case_id)
    if not meta.exists():
        raise FileNotFoundError("Case meta not found")
    return json.loads(meta.read_text(encoding="utf-8"))


def write_case_meta(paths: StoragePaths, case_id: str, meta: Dict[str, Any]) -> None:
    ensure_case_structure(paths, case_id)
    paths.meta_path(case_id).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def append_audit(paths: StoragePaths, case_id: str, event_type: str, payload: Dict[str, Any]) -> None:
    ensure_case_structure(paths, case_id)
    line = json.dumps(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "payload": payload,
        },
        ensure_ascii=False,
    )
    with paths.audit_path(case_id).open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_version_files(paths: StoragePaths, draft: RiskCaseDraft) -> None:
    ensure_case_structure(paths, draft.case_id)
    dpath = paths.draft_path(draft.case_id, draft.version)
    dpath.write_text(draft.model_dump_json(indent=2), encoding="utf-8")


def read_version_draft(paths: StoragePaths, case_id: str, version: int) -> RiskCaseDraft:
    dpath = paths.draft_path(case_id, version)
    if not dpath.exists():
        raise FileNotFoundError("Draft not found")
    return RiskCaseDraft.model_validate_json(dpath.read_text(encoding="utf-8"))


def write_snapshot(paths: StoragePaths, case_id: str, version: int, snapshot_json: str) -> None:
    spath = paths.snapshot_path(case_id, version)
    spath.write_text(snapshot_json, encoding="utf-8")


def write_decision(paths: StoragePaths, case_id: str, version: int, decision_json: str) -> None:
    dpath = paths.decision_path(case_id, version)
    dpath.write_text(decision_json, encoding="utf-8")
