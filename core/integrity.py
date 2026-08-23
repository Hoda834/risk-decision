from __future__ import annotations

from typing import Any, Dict, List

from core.engine import hashable_inputs
from core.storage import StoragePaths, verify_audit_log
from core.utils import stable_hash


def snapshot_matches_inputs(payload: Dict[str, Any]) -> bool:
    """True when the stored snapshot still describes the stored inputs."""
    snapshot = payload.get("evaluation_snapshot")
    if not isinstance(snapshot, dict) or not snapshot.get("inputs_hash"):
        return True
    return str(snapshot["inputs_hash"]) == stable_hash(hashable_inputs(payload))


def check_case(paths: StoragePaths, payload: Dict[str, Any]) -> List[str]:
    """Integrity problems worth showing the reader before they trust the case.

    Writing a hash and never checking it is theatre. This runs on load.
    """
    problems: List[str] = []

    if not snapshot_matches_inputs(payload):
        problems.append(
            "The stored inputs no longer match the hash recorded at evaluation. "
            "This case was edited after it was locked."
        )

    case_id = str(payload.get("case_id", ""))
    if case_id:
        broken_at = verify_audit_log(paths, case_id)
        if broken_at is not None:
            problems.append(
                f"The audit log breaks its hash chain at entry {broken_at + 1}. "
                "Entries were edited or removed."
            )

    return problems
