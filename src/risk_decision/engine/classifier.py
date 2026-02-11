from __future__ import annotations

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
