from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


_DRAFT_RE = re.compile(r"^draft_v(\d+)\.json$")


@dataclass(frozen=True)
class CasePaths:
    """
    Simple on-disk storage for Streamlit Cloud.

    Layout:
      <root>/data/cases/<case_id>/draft_v<version>.json
    """
    root: Path
    cases_dir: Path


def init_case_paths(base_dir: str | Path) -> CasePaths:
    root = Path(base_dir).resolve()
    cases_dir = root / "data" / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    return CasePaths(root=root, cases_dir=cases_dir)


def _case_dir(paths: CasePaths, case_id: str) -> Path:
    return paths.cases_dir / case_id


def _draft_path(paths: CasePaths, case_id: str, version: int) -> Path:
    return _case_dir(paths, case_id) / f"draft_v{int(version)}.json"


def _latest_version(paths: CasePaths, case_id: str) -> Optional[int]:
    cdir = _case_dir(paths, case_id)
    if not cdir.exists():
        return None

    best: Optional[int] = None
    for p in cdir.iterdir():
        if not p.is_file():
            continue
        m = _DRAFT_RE.match(p.name)
        if not m:
            continue
        v = int(m.group(1))
        if best is None or v > best:
            best = v
    return best


def list_cases(paths: CasePaths) -> List[Dict[str, Any]]:
    """
    Returns a list of lightweight dicts:
      { "case_id": str, "latest_version": int, "anchor": { "name": str } }
    """
    out: List[Dict[str, Any]] = []
    if not paths.cases_dir.exists():
        return out

    for cdir in sorted(paths.cases_dir.iterdir()):
        if not cdir.is_dir():
            continue
        case_id = cdir.name
        v = _latest_version(paths, case_id)
        if v is None:
            continue

        try:
            payload = read_draft(paths, case_id, v)
        except Exception:
            payload = {}

        anchor = payload.get("anchor") if isinstance(payload, dict) else {}
        if not isinstance(anchor, dict):
            anchor = {}

        out.append(
            {
                "case_id": case_id,
                "latest_version": v,
                "anchor": {"name": (anchor.get("name") or "").strip()},
                "case_name": (anchor.get("name") or "").strip(),
            }
        )

    return out


def read_draft(paths: CasePaths, case_id: str, version: Optional[int] = None) -> Dict[str, Any]:
    v = int(version) if version is not None else _latest_version(paths, case_id)
    if v is None:
        raise FileNotFoundError(f"No draft found for case_id={case_id}")

    p = _draft_path(paths, case_id, v)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Draft content is not a JSON object.")
    return data


def write_draft(paths: CasePaths, case_id: str, version: int, content: str) -> Path:
    """
    Writes JSON content (string) to draft file.
    Uses atomic replace to reduce corruption on reruns.
    """
    cdir = _case_dir(paths, case_id)
    cdir.mkdir(parents=True, exist_ok=True)

    target = _draft_path(paths, case_id, int(version))
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)
    return target
