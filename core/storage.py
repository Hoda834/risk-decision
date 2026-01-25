from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.models import RiskCaseDraft


@dataclass(frozen=True)
class StoragePaths:
    root: Path

    @property
    def cases_dir(self) -> Path:
        return self.root / "cases"

    @property
    def drafts_dir(self) -> Path:
        return self.root / "drafts"

    @property
    def snapshots_dir(self) -> Path:
        return self.root / "snapshots"

    @property
    def decisions_dir(self) -> Path:
        return self.root / "decisions"

    def case_dir(self, case_id: str) -> Path:
        return self.cases_dir / case_id

    def case_meta_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "meta.json"

    def case_audit_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "audit.log.jsonl"

    def draft_dir(self, case_id: str) -> Path:
        return self.drafts_dir / case_id

    def draft_path(self, case_id: str, version: int) -> Path:
        return self.draft_dir(case_id) / f"v{version}.json"

    def snapshot_path(self, case_id: str, version: int) -> Path:
        return self.snapshots_dir / case_id / f"v{version}.json"

    def decision_path(self, case_id: str, version: int) -> Path:
        return self.decisions_dir / case_id / f"v{version}.json"


CasePaths = StoragePaths


def init_case_paths(base_dir: str = ".") -> StoragePaths:
    paths = StoragePaths(Path(base_dir).resolve())
    ensure_case_structure(paths)
    return paths


def ensure_case_structure(paths: StoragePaths) -> None:
    paths.cases_dir.mkdir(parents=True, exist_ok=True)
    paths.drafts_dir.mkdir(parents=True, exist_ok=True)
    paths.snapshots_dir.mkdir(parents=True, exist_ok=True)
    paths.decisions_dir.mkdir(parents=True, exist_ok=True)


def list_cases(paths: StoragePaths) -> List[Dict[str, Any]]:
    ensure_case_structure(paths)
    out: List[Dict[str, Any]] = []
    for case_dir in sorted(paths.cases_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        case_id = case_dir.name
        meta = read_case_meta(paths, case_id)
        item = {"case_id": case_id}
        if isinstance(meta, dict):
            item.update(meta)
        out.append(item)
    return out


def list_case_versions(paths: StoragePaths, case_id: str) -> List[int]:
    ddir = paths.draft_dir(case_id)
    if not ddir.exists():
        return []
    versions: List[int] = []
    for p in ddir.glob("v*.json"):
        try:
            v = int(p.stem.lstrip("v"))
            versions.append(v)
        except ValueError:
            continue
    return sorted(set(versions))


def read_version_draft(paths: StoragePaths, case_id: str, version: int) -> Dict[str, Any]:
    p = paths.draft_path(case_id, version)
    if not p.exists():
        raise FileNotFoundError(f"Draft not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def read_draft(paths: StoragePaths, case_id: str, version: Optional[int] = None) -> Dict[str, Any]:
    versions = list_case_versions(paths, case_id)
    if not versions:
        raise FileNotFoundError("No draft versions found for this case.")
    v = version if version is not None else versions[-1]
    return read_version_draft(paths, case_id, v)


def write_draft(paths: StoragePaths, case_id: str, version: int, payload: Union[Dict[str, Any], str]) -> None:
    ensure_case_structure(paths)
    paths.draft_dir(case_id).mkdir(parents=True, exist_ok=True)

    if isinstance(payload, str):
        content = payload
        json.loads(content)
    else:
        content = json.dumps(payload, indent=2, ensure_ascii=False)

    paths.draft_path(case_id, version).write_text(content, encoding="utf-8")


def write_case_meta(paths: StoragePaths, case_id: str, meta: Dict[str, Any]) -> None:
    ensure_case_structure(paths)
    paths.case_dir(case_id).mkdir(parents=True, exist_ok=True)
    paths.case_meta_path(case_id).write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def read_case_meta(paths: StoragePaths, case_id: str) -> Optional[Dict[str, Any]]:
    p = paths.case_meta_path(case_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def append_audit(paths: StoragePaths, case_id: str, event: Dict[str, Any]) -> None:
    ensure_case_structure(paths)
    paths.case_dir(case_id).mkdir(parents=True, exist_ok=True)
    p = paths.case_audit_path(case_id)
    event = dict(event)
    event.setdefault("ts", datetime.now(timezone.utc).isoformat())
    if not p.exists():
        p.write_text("", encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def write_version_files(paths: StoragePaths, case_id: str, version: int, draft: RiskCaseDraft) -> None:
    payload = draft.model_dump()
    write_draft(paths, case_id, version, payload)


def write_snapshot(paths: StoragePaths, case_id: str, version: int, snapshot: Dict[str, Any]) -> None:
    ensure_case_structure(paths)
    outdir = paths.snapshot_path(case_id, version).parent
    outdir.mkdir(parents=True, exist_ok=True)
    paths.snapshot_path(case_id, version).write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")


def write_decision(paths: StoragePaths, case_id: str, version: int, decision: Dict[str, Any]) -> None:
    ensure_case_structure(paths)
    outdir = paths.decision_path(case_id, version).parent
    outdir.mkdir(parents=True, exist_ok=True)
    paths.decision_path(case_id, version).write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
