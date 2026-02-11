
from dataclasses import dataclass
from typing import Dict
from typing import Literal


RiskAppetite = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Thresholds:
    low: float
    high: float


class BasicClassifier:
    def __init__(self, low_threshold: float = 20.0, high_threshold: float = 45.0):
        self.low_threshold = float(low_threshold)
        self.high_threshold = float(high_threshold)

    def classify(self, domain_scores: Dict[str, float]) -> Dict[str, Dict[str, float | str]]:
        classifications: Dict[str, Dict[str, float | str]] = {}

        for domain, score in domain_scores.items():
            s = float(score)

            if s < self.low_threshold:
                level = "low"
            elif s < self.high_threshold:
                level = "medium"
            else:
                level = "high"

            classifications[domain] = {
                "score": s,
                "level": level,
            }

        return classifications


class PolicyAwareClassifier:
    """
    Classifier with appetite- and stage-aware threshold adjustment.
    """

    def __init__(
        self,
        base_low_threshold: float = 20.0,
        base_high_threshold: float = 45.0,
        risk_appetite: RiskAppetite = "medium",
        stage: str | None = None,
    ):
        self.base_low = float(base_low_threshold)
        self.base_high = float(base_high_threshold)
        self.risk_appetite: RiskAppetite = risk_appetite
        self.stage = (stage or "").strip().lower() or None

        if self.base_low <= 0 or self.base_high <= 0 or self.base_low >= self.base_high:
            raise ValueError("Invalid base thresholds: require 0 < base_low < base_high")

    def _thresholds(self) -> Thresholds:
        if self.risk_appetite == "low":
            scale = 0.85
        elif self.risk_appetite == "high":
            scale = 1.15
        else:
            scale = 1.0

        low_t = self.base_low * scale
        high_t = self.base_high * scale

        if self.stage in {"concept", "design"}:
            low_t *= 0.95
            high_t *= 0.95

        if low_t >= high_t:
            high_t = low_t + 1e-6

        return Thresholds(low=low_t, high=high_t)

    def classify(self, domain_scores: Dict[str, float]) -> Dict[str, Dict[str, float | str | Dict[str, float] | Dict[str, str | None]]]:
        thresholds = self._thresholds()
        classifications: Dict[str, Dict[str, float | str | Dict[str, float] | Dict[str, str | None]]] = {}

        for domain, score in domain_scores.items():
            s = float(score)

            if s < thresholds.low:
                level = "low"
            elif s < thresholds.high:
                level = "medium"
            else:
                level = "high"

            classifications[domain] = {
                "score": s,
                "level": level,
                "thresholds": {"low": thresholds.low, "high": thresholds.high},
                "policy": {"risk_appetite": self.risk_appetite, "stage": self.stage},
            }

        return classifications
src/risk_decision/engine/scorer.py
src/risk_decision/engine/scorer.py
+10
-114

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal
from typing import Any, Dict


RiskAppetite = Literal["low", "medium", "high"]
class BasicScorer:
    """Baseline scorer that accepts precomputed local scores from the payload."""

    def score(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        indicator_details = payload.get("indicator_details", {}) if isinstance(payload, dict) else {}
        local_scores = payload.get("local_scores", {}) if isinstance(payload, dict) else {}

@dataclass(frozen=True)
class Thresholds:
    low: float
    high: float


class BasicClassifier:
    """
    v1 classifier: absolute thresholds, context-blind.
    Kept for baseline behaviour and regression tests.
    """
    def __init__(self, low_threshold: float = 20.0, high_threshold: float = 45.0):
        self.low_threshold = float(low_threshold)
        self.high_threshold = float(high_threshold)

    def classify(self, domain_scores: Dict[str, float]) -> Dict[str, Dict[str, float | str]]:
        classifications: Dict[str, Dict[str, float | str]] = {}

        for domain, score in domain_scores.items():
            s = float(score)

            if s < self.low_threshold:
                level = "low"
            elif s < self.high_threshold:
                level = "medium"
            else:
                level = "high"

            classifications[domain] = {"score": s, "level": level}

        return classifications


class PolicyAwareClassifier:
    """
    v2 classifier: appetite-aware thresholds.

    The engine stays data-agnostic (scoring semantics can be user-defined),
    but classification becomes policy-aware, which is where governance belongs.
    """
    def __init__(
        self,
        base_low_threshold: float = 20.0,
        base_high_threshold: float = 45.0,
        risk_appetite: RiskAppetite = "medium",
        stage: str | None = None,
    ):
        self.base_low = float(base_low_threshold)
        self.base_high = float(base_high_threshold)
        self.risk_appetite: RiskAppetite = risk_appetite
        self.stage = (stage or "").strip().lower() or None

        if self.base_low <= 0 or self.base_high <= 0 or self.base_low >= self.base_high:
            raise ValueError("Invalid base thresholds: require 0 < base_low < base_high")

    def _thresholds(self) -> Thresholds:
        """
        Appetite scaling logic:

        - low appetite: stricter (classify 'medium/high' earlier)
        - high appetite: looser (tolerate higher scores before escalating)

        Scaling is applied to both thresholds to preserve separation.
        """
        appetite = self.risk_appetite

        if appetite == "low":
            scale = 0.85
        elif appetite == "high":
            scale = 1.15
        else:
            scale = 1.00

        low_t = self.base_low * scale
        high_t = self.base_high * scale

        # Optional stage sensitivity: earlier stages can be stricter by default.
        # Keep conservative and simple in v2.
        if self.stage in {"concept", "design"}:
            low_t *= 0.95
            high_t *= 0.95

        # Ensure ordering remains valid
        if low_t >= high_t:
            high_t = low_t + 1e-6

        return Thresholds(low=low_t, high=high_t)

    def classify(self, domain_scores: Dict[str, float]) -> Dict[str, Dict[str, float | str]]:
        t = self._thresholds()
        classifications: Dict[str, Dict[str, float | str]] = {}

        for domain, score in domain_scores.items():
            s = float(score)

            if s < t.low:
                level = "low"
            elif s < t.high:
                level = "medium"
            else:
                level = "high"

            classifications[domain] = {
                "score": s,
                "level": level,
                # include thresholds for transparency/debugging (harmless for consumers)
                "thresholds": {"low": t.low, "high": t.high},
                "policy": {"risk_appetite": self.risk_appetite, "stage": self.stage},
            }

        return classifications
        return {
            "indicator_details": dict(indicator_details or {}),
            "local_scores": {str(k): float(v) for k, v in dict(local_scores or {}).items()},
        }
