from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class PolicyConfig:
    raw: Dict[str, Any]

    @property
    def policy_version(self) -> str:
        return str(self.raw.get("policy_version", "v0"))

    def likelihood_labels(self) -> Dict[str, str]:
        return dict(self.raw["scales"]["likelihood"]["labels"])

    def impact_labels(self) -> Dict[str, str]:
        return dict(self.raw["scales"]["impact"]["labels"])

    def normalise_likelihood(self, value: int) -> float:
        norm = self.raw["scales"]["likelihood"]["normalisation"]
        vmin = float(norm["min"])
        vmax = float(norm["max"])
        return self._minmax(value, vmin, vmax)

    def normalise_impact(self, value: int) -> float:
        norm = self.raw["scales"]["impact"]["normalisation"]
        vmin = float(norm["min"])
        vmax = float(norm["max"])
        return self._minmax(value, vmin, vmax)

    def score(self, likelihood_norm: float, impact_norm: float) -> float:
        method = str(self.raw["scoring"]["method"])
        decimals = int(self.raw["scoring"]["rounding"]["decimals"])
        if method == "multiply":
            s = float(likelihood_norm) * float(impact_norm)
        else:
            s = float(likelihood_norm) * float(impact_norm)
        return round(s, decimals)

    def classify(self, score: float) -> str:
        cats = list(self.raw["thresholds"]["categories"])
        for c in cats:
            if float(c["min"]) <= float(score) < float(c["max"]):
                return str(c["name"])
        return str(cats[-1]["name"])

    def acceptance_threshold(self) -> float:
        return float(self.raw["thresholds"]["acceptance_threshold"])

    def hard_accept_block_threshold(self) -> float:
        return float(self.raw["thresholds"]["hard_accept_block_threshold"])

    def recommend_decision(self, score: float) -> str:
        rules = list(self.raw["decision_policy"]["recommended"])
        for r in rules:
            if "if_score_lt" in r and score < float(r["if_score_lt"]):
                return str(r["decision"])
            if "if_score_gte" in r and score >= float(r["if_score_gte"]):
                return str(r["decision"])
        return "reduce"

    def authority_max_score(self, role: str) -> float:
        matrix = list(self.raw.get("escalation", {}).get("authority_matrix", []))
        for row in matrix:
            if str(row["role"]) == role:
                return float(row["max_score_to_accept"])
        return 0.0

    def privacy_keywords(self) -> List[str]:
        return list(self.raw.get("branching", {}).get("signals", {}).get("privacy_keywords", []))

    def catastrophic_if_impact_level_gte(self) -> int:
        return int(self.raw.get("branching", {}).get("signals", {}).get("catastrophic_if_impact_level_gte", 3))

    @staticmethod
    def _minmax(value: float, vmin: float, vmax: float) -> float:
        if vmax <= vmin:
            return 0.0
        x = (float(value) - vmin) / (vmax - vmin)
        if x < 0:
            return 0.0
        if x > 1:
            return 1.0
        return float(x)


def load_policy(path: Path) -> PolicyConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    _validate_policy(raw)
    return PolicyConfig(raw=raw)


def _validate_policy(raw: Dict[str, Any]) -> None:
    for k in ["scales", "scoring", "thresholds", "decision_policy"]:
        if k not in raw:
            raise ValueError(f"Missing policy key: {k}")
    for s in ["likelihood", "impact"]:
        if s not in raw["scales"]:
            raise ValueError(f"Missing scale: {s}")
        if "labels" not in raw["scales"][s]:
            raise ValueError(f"Missing labels for: {s}")
        if "normalisation" not in raw["scales"][s]:
            raise ValueError(f"Missing normalisation for: {s}")
    if raw["scoring"].get("method") not in {"multiply"}:
        raise ValueError("Unsupported scoring method")
    if "categories" not in raw["thresholds"]:
        raise ValueError("Missing thresholds categories")
    cats = raw["thresholds"]["categories"]
    if not isinstance(cats, list) or len(cats) < 1:
        raise ValueError("Threshold categories invalid")
