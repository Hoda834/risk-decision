from __future__ import annotations

from typing import Any, Dict


class BasicScorer:
    """Baseline scorer that accepts precomputed local scores from the payload."""

    def score(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        indicator_details = payload.get("indicator_details", {}) if isinstance(payload, dict) else {}
        local_scores = payload.get("local_scores", {}) if isinstance(payload, dict) else {}

        return {
            "indicator_details": dict(indicator_details or {}),
            "local_scores": {str(k): float(v) for k, v in dict(local_scores or {}).items()},
        }
