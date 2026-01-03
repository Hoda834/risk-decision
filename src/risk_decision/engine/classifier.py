from __future__ import annotations

from typing import Dict


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

