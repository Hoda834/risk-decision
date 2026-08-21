from __future__ import annotations

from typing import Any, Dict


class BasicScorer:
    """Baseline scorer.

    Accepts precomputed local scores from the payload and passes them through
    unchanged. Scoring semantics stay with the caller, so the engine remains
    data agnostic.
    """

    def score(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {"indicator_details": {}, "local_scores": {}}

        indicator_details = payload.get("indicator_details") or {}
        local_scores = payload.get("local_scores") or {}

        return {
            "indicator_details": {str(k): dict(v) for k, v in dict(indicator_details).items()},
            "local_scores": {str(k): float(v) for k, v in dict(local_scores).items()},
        }
