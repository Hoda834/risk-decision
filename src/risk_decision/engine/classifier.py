from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal


RiskAppetite = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Thresholds:
    low: float
    high: float


def _level_for(score: float, thresholds: Thresholds) -> str:
    if score < thresholds.low:
        return "low"
    if score < thresholds.high:
        return "medium"
    return "high"


class BasicClassifier:
    """v1 classifier: absolute thresholds, context blind.

    Kept as the baseline for regression tests.
    """

    def __init__(self, low_threshold: float = 20.0, high_threshold: float = 45.0):
        self.low_threshold = float(low_threshold)
        self.high_threshold = float(high_threshold)

        if self.low_threshold >= self.high_threshold:
            raise ValueError("Invalid thresholds: require low_threshold < high_threshold")

    def classify(self, domain_scores: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        thresholds = Thresholds(low=self.low_threshold, high=self.high_threshold)
        return {
            domain: {
                "score": float(score),
                "level": _level_for(float(score), thresholds),
                "thresholds": {"low": thresholds.low, "high": thresholds.high},
            }
            for domain, score in domain_scores.items()
        }


class PolicyAwareClassifier:
    """v2 classifier: appetite and stage aware thresholds.

    Scoring stays data agnostic. Classification is where governance belongs,
    so appetite and project stage move the thresholds rather than the scores.
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
            scale = 1.00

        low_t = self.base_low * scale
        high_t = self.base_high * scale

        if self.stage in {"concept", "design"}:
            low_t *= 0.95
            high_t *= 0.95

        if low_t >= high_t:
            high_t = low_t + 1e-6

        return Thresholds(low=low_t, high=high_t)

    def classify(self, domain_scores: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        thresholds = self._thresholds()
        classifications: Dict[str, Dict[str, Any]] = {}

        for domain, score in domain_scores.items():
            s = float(score)
            classifications[domain] = {
                "score": s,
                "level": _level_for(s, thresholds),
                "thresholds": {"low": thresholds.low, "high": thresholds.high},
                "policy": {"risk_appetite": self.risk_appetite, "stage": self.stage},
            }

        return classifications
