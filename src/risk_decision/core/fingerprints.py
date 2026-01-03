from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def _stable_serialize(obj: Any) -> str:
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except TypeError:
        return json.dumps(str(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_object(obj: Any) -> str:
    serialized = _stable_serialize(obj)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_fingerprints(
    payload: Dict[str, Any],
    config: Dict[str, Any],
    model_ref: str = "",
) -> Dict[str, str]:
    return {
        "input_hash": hash_object(payload),
        "config_hash": hash_object(config),
        "model_hash": model_ref or "",
    }

