from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.models import RiskCaseDraft

DEFAULT_DATA_DIR = "data"

_SAFE_CASE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _check_case_id(case_id: str) -> str:
    """Case ids become directory names, so they never contain a path."""
    if not _SAFE_CASE_ID.match(str(case_id)):
        raise ValueError(f"Unsafe case id: {case_id!r}")
    return str(case_id)


@dataclass(frozen=True)
class StoragePaths:
    root: Path

    def __post_init__(self) -> None:
        # A string root fails several calls later with an unrelated error.
        object.__setattr__(self, "root", Path(self.root))

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
        return self.cases_dir / _check_case_id(case_id)

    def case_meta_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "meta.json"

    def case_audit_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "audit.log.jsonl"

    def draft_dir(self, case_id: str) -> Path:
        return self.drafts_dir / _check_case_id(case_id)

    def draft_path(self, case_id: str, version: int) -> Path:
        return self.draft_dir(case_id) / f"v{version}.json"

    def snapshot_path(self, case_id: str, version: int) -> Path:
        return self.snapshots_dir / _check_case_id(case_id) / f"v{version}.json"

    def decision_path(self, case_id: str, version: int) -> Path:
        return self.decisions_dir / _check_case_id(case_id) / f"v{version}.json"


CasePaths = StoragePaths


def init_case_paths(base_dir: str = DEFAULT_DATA_DIR) -> StoragePaths:
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
    if not paths.cases_dir.exists():
        return out
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


class LockedVersionError(RuntimeError):
    """Raised when a locked version's assessed inputs would change."""


def write_draft(paths: StoragePaths, case_id: str, version: int, payload: Union[Dict[str, Any], str]) -> None:
    ensure_case_structure(paths)
    paths.draft_dir(case_id).mkdir(parents=True, exist_ok=True)

    if isinstance(payload, str):
        content = payload
        data = json.loads(content)
    else:
        data = payload
        content = json.dumps(payload, indent=2, ensure_ascii=False)

    _refuse_if_locked_inputs_changed(paths, case_id, version, data)
    paths.draft_path(case_id, version).write_text(content, encoding="utf-8")


def _refuse_if_locked_inputs_changed(
    paths: StoragePaths,
    case_id: str,
    version: int,
    incoming: Dict[str, Any],
) -> None:
    """A locked version keeps its inputs. Revising means a new version.

    Recording or overriding a decision is still allowed, because that changes the
    decision block and not the assessment behind it.
    """
    path = paths.draft_path(case_id, version)
    if not path.exists():
        return

    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    if not (existing.get("wizard") or {}).get("locked_at_end"):
        return
    if not (incoming.get("wizard") or {}).get("locked_at_end"):
        return

    from core.engine import hashable_inputs

    if hashable_inputs(existing) != hashable_inputs(incoming):
        raise LockedVersionError(
            f"Case {case_id} version {version} is locked. "
            "Revise it as a new version instead of editing the assessed inputs."
        )


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


GENESIS_HASH = "0" * 64


def _entry_hash(prev_hash: str, event: Dict[str, Any]) -> str:
    body = {k: v for k, v in event.items() if k != "entry_hash"}
    payload = prev_hash + json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_audit(paths: StoragePaths, case_id: str) -> List[Dict[str, Any]]:
    p = paths.case_audit_path(case_id)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def append_audit(paths: StoragePaths, case_id: str, event: Dict[str, Any]) -> None:
    """Append one hash-chained entry.

    Each entry carries the hash of the one before it, so an edited or removed
    line breaks the chain instead of passing unnoticed.
    """
    ensure_case_structure(paths)
    paths.case_dir(case_id).mkdir(parents=True, exist_ok=True)
    p = paths.case_audit_path(case_id)

    existing = read_audit(paths, case_id)
    prev_hash = str(existing[-1].get("entry_hash", GENESIS_HASH)) if existing else GENESIS_HASH

    event = dict(event)
    event.setdefault("ts", datetime.now(timezone.utc).isoformat())
    event["prev_hash"] = prev_hash
    event["entry_hash"] = _entry_hash(prev_hash, event)

    if not p.exists():
        p.write_text("", encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def verify_audit_log(paths: StoragePaths, case_id: str) -> Optional[int]:
    """Return the index of the first broken entry, or None when the chain holds."""
    prev_hash = GENESIS_HASH
    for index, entry in enumerate(read_audit(paths, case_id)):
        if str(entry.get("prev_hash")) != prev_hash:
            return index
        if str(entry.get("entry_hash")) != _entry_hash(prev_hash, entry):
            return index
        prev_hash = str(entry["entry_hash"])
    return None


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
