from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.models import DecisionType

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "policy_config.json"


@dataclass(frozen=True)
class PolicyConfig:
    raw: Dict[str, Any]

    @property
    def policy_version(self) -> str:
        return str(self.raw.get("policy_version", "v0"))

    def likelihood_labels(self) -> Dict[int, str]:
        return {int(k): str(v) for k, v in self.raw["scales"]["likelihood"]["labels"].items()}

    def impact_labels(self) -> Dict[int, str]:
        return {int(k): str(v) for k, v in self.raw["scales"]["impact"]["labels"].items()}

    def scale_bounds(self, dimension: str) -> tuple[int, int]:
        norm = self.raw["scales"][dimension]["normalisation"]
        return int(norm["min"]), int(norm["max"])

    def normalise_likelihood(self, value: int) -> float:
        vmin, vmax = self.scale_bounds("likelihood")
        return self._minmax(value, vmin, vmax)

    def normalise_impact(self, value: int) -> float:
        vmin, vmax = self.scale_bounds("impact")
        return self._minmax(value, vmin, vmax)

    def score(self, likelihood_norm: float, impact_norm: float) -> float:
        method = str(self.raw["scoring"]["method"])
        decimals = int(self.raw["scoring"]["rounding"]["decimals"])
        if method != "multiply":
            raise ValueError(f"Unsupported scoring method: {method}")
        return round(float(likelihood_norm) * float(impact_norm), decimals)

    def category_names(self) -> List[str]:
        return [str(c["name"]) for c in self.raw["thresholds"]["categories"]]

    def classify(self, score: float) -> str:
        for c in self.raw["thresholds"]["categories"]:
            if float(c["min"]) <= float(score) < float(c["max"]):
                return str(c["name"])
        return self.category_names()[-1]

    def category_rank(self, name: str) -> int:
        names = self.category_names()
        return names.index(name) if name in names else 0

    def floor_category(self, current: str, floor: Optional[str]) -> str:
        """Raise a category to a floor. Never lowers it."""
        if not floor:
            return current
        return floor if self.category_rank(floor) > self.category_rank(current) else current

    def overrides(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.raw.get("overrides", {}))

    def acceptance_threshold(self) -> float:
        return float(self.raw["thresholds"]["acceptance_threshold"])

    def hard_accept_block_threshold(self) -> float:
        return float(self.raw["thresholds"]["hard_accept_block_threshold"])

    def escalation_score_threshold(self) -> float:
        return float(self.raw.get("escalation", {}).get("require_approval_if", {}).get("score_gte", 1.01))

    def escalate_on_any_override(self) -> bool:
        return bool(self.raw.get("escalation", {}).get("require_approval_if", {}).get("any_override_applied", False))

    def recommend_decision(self, category: str) -> DecisionType:
        mapping = self.raw["decision_policy"]["by_category"]
        if category not in mapping:
            raise ValueError(f"No decision mapped for category: {category}")
        return DecisionType(str(mapping[category]).upper())

    def override_requires_note(self) -> bool:
        return bool(self.raw["decision_policy"].get("constraints", {}).get("override_requires_note", True))

    def authority_max_score(self, role: str) -> float:
        for row in self.raw.get("escalation", {}).get("authority_matrix", []):
            if str(row["role"]) == role:
                return float(row["max_score_to_accept"])
        return 0.0

    @staticmethod
    def _minmax(value: float, vmin: float, vmax: float) -> float:
        if vmax <= vmin:
            raise ValueError("Invalid normalisation bounds: require min < max")
        x = (float(value) - float(vmin)) / (float(vmax) - float(vmin))
        return min(1.0, max(0.0, x))


def load_policy(path: Optional[Path] = None) -> PolicyConfig:
    p = Path(path) if path is not None else DEFAULT_POLICY_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    _validate_policy(raw)
    return PolicyConfig(raw=raw)


def _validate_policy(raw: Dict[str, Any]) -> None:
    for key in ("scales", "scoring", "thresholds", "decision_policy"):
        if key not in raw or not raw[key]:
            raise ValueError(f"Missing or empty policy key: {key}")

    for dimension in ("likelihood", "impact"):
        scale = raw["scales"].get(dimension)
        if not scale:
            raise ValueError(f"Missing scale: {dimension}")
        if "labels" not in scale:
            raise ValueError(f"Missing labels for: {dimension}")
        if "normalisation" not in scale:
            raise ValueError(f"Missing normalisation for: {dimension}")

        norm = scale["normalisation"]
        vmin, vmax = int(norm["min"]), int(norm["max"])
        if vmin >= vmax:
            raise ValueError(f"Invalid bounds for {dimension}: require min < max")

        points = {int(k) for k in scale["labels"]}
        expected = set(range(vmin, vmax + 1))
        if points != expected:
            missing = sorted(expected - points)
            extra = sorted(points - expected)
            raise ValueError(
                f"Labels for {dimension} must cover every point from {vmin} to {vmax}. "
                f"Missing: {missing}. Unexpected: {extra}."
            )

    if raw["scoring"].get("method") != "multiply":
        raise ValueError("Unsupported scoring method")
    if "rounding" not in raw["scoring"]:
        raise ValueError("Missing scoring rounding")

    cats = raw["thresholds"].get("categories")
    if not isinstance(cats, list) or not cats:
        raise ValueError("Threshold categories invalid")

    if float(cats[0]["min"]) > 0.0:
        raise ValueError("Threshold categories must start at 0.0")
    for previous, nxt in zip(cats, cats[1:]):
        if float(previous["max"]) != float(nxt["min"]):
            raise ValueError(
                f"Threshold categories leave a gap between {previous['name']} and {nxt['name']}"
            )
    if float(cats[-1]["max"]) <= 1.0:
        raise ValueError("Threshold categories must cover a score of 1.0")

    mapping = raw["decision_policy"].get("by_category")
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("Missing decision_policy.by_category")
    for cat in cats:
        name = str(cat["name"])
        if name not in mapping:
            raise ValueError(f"No decision mapped for category: {name}")
        try:
            DecisionType(str(mapping[name]).upper())
        except ValueError as exc:
            raise ValueError(f"Unknown decision for category {name}: {mapping[name]}") from exc

    for name, rule in dict(raw.get("overrides", {})).items():
        floor = rule.get("floor_category")
        if floor is not None and floor not in {str(c["name"]) for c in cats}:
            raise ValueError(f"Override {name} floors to an unknown category: {floor}")
