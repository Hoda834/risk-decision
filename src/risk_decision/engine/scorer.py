from __future__ import annotations

from typing import Any, Dict


class BasicScorer:
    def score(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        indicator_details = payload.get("indicator_details", {}) or {}
        local_scores = payload.get("local_scores", {}) or {}

        return {
            "indicator_details": dict(indicator_details),
            "local_scores": dict(local_scores),
        }

