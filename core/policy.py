from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.models import DecisionType

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "policy_config.json"


@dataclass(frozen=True)
class PolicyConfig:
    raw: Dict[str, Any]

    @property
    def policy_version(self) -> str:
        return str(self.raw.get("policy_version", "v0"))

    # ------------------------------------------------------------------ scales

    def likelihood_labels(self) -> Dict[int, str]:
        return {int(k): str(v) for k, v in self.raw["scales"]["likelihood"]["labels"].items()}

    def impact_labels(self) -> Dict[int, str]:
        return {int(k): str(v) for k, v in self.raw["scales"]["impact"]["labels"].items()}

    def scale_bounds(self, dimension: str) -> Tuple[int, int]:
        norm = self.raw["scales"][dimension]["normalisation"]
        return int(norm["min"]), int(norm["max"])

    def scale_points(self, dimension: str) -> List[int]:
        vmin, vmax = self.scale_bounds(dimension)
        return list(range(vmin, vmax + 1))

    def normalise_likelihood(self, value: int) -> float:
        vmin, vmax = self.scale_bounds("likelihood")
        return self._minmax(value, vmin, vmax)

    def normalise_impact(self, value: int) -> float:
        vmin, vmax = self.scale_bounds("impact")
        return self._minmax(value, vmin, vmax)

    # ----------------------------------------------------------- categorisation

    def category_from_matrix(self, likelihood: int, impact: int) -> str:
        """Category comes from an explicit cell, not from arithmetic.

        Likelihood and impact are ordinal labels. Multiplying them assumes a
        distance between points that the scale does not define, so the cell is
        the governance decision and the score is only an ordering aid.
        """
        cells = self.raw["scoring"]["category_matrix"]["cells"]
        row = cells.get(str(int(likelihood)))
        if row is None:
            raise ValueError(f"No matrix row for likelihood {likelihood}")
        points = self.scale_points("impact")
        if int(impact) not in points:
            raise ValueError(f"Impact {impact} is outside the scale")
        return str(row[points.index(int(impact))])

    def ordering_score(self, likelihood: int, impact: int) -> float:
        """A 0 to 1 value for sorting within and across categories."""
        method = str(self.raw["scoring"]["ordering_score"]["method"])
        decimals = int(self.raw["scoring"]["ordering_score"]["rounding"]["decimals"])
        lmin, lmax = self.scale_bounds("likelihood")
        imin, imax = self.scale_bounds("impact")

        if method != "ordinal_product":
            raise ValueError(f"Unsupported ordering score method: {method}")

        low = lmin * imin
        high = lmax * imax
        value = (int(likelihood) * int(impact) - low) / (high - low)
        return round(min(1.0, max(0.0, value)), decimals)

    def category_names(self) -> List[str]:
        return [str(c["name"]) for c in self.raw["thresholds"]["categories"]]

    def classify(self, score: float) -> str:
        """Band lookup for a 0 to 1 score. Used for display ordering only."""
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

    # -------------------------------------------------------------- escalation

    def _escalation_rules(self) -> Dict[str, Any]:
        return dict(self.raw.get("escalation", {}).get("require_approval_if", {}))

    def escalation_categories(self) -> List[str]:
        return [str(c) for c in self._escalation_rules().get("category_in", [])]

    def escalate_on_any_override(self) -> bool:
        return bool(self._escalation_rules().get("any_override_applied", False))

    def escalation_confidence_floor(self) -> Optional[int]:
        value = self._escalation_rules().get("confidence_lte")
        return int(value) if value is not None else None

    # --------------------------------------------------------------- decisions

    def recommend_decision(self, category: str) -> DecisionType:
        mapping = self.raw["decision_policy"]["by_category"]
        if category not in mapping:
            raise ValueError(f"No decision mapped for category: {category}")
        return DecisionType(str(mapping[category]).upper())

    def constraints(self) -> Dict[str, Any]:
        return dict(self.raw["decision_policy"].get("constraints", {}))

    def override_requires_note(self) -> bool:
        return bool(self.constraints().get("override_requires_note", True))

    def accept_requires_review_date(self) -> bool:
        return bool(self.constraints().get("accept_requires_review_date", True))

    def escalation_requires_second_person(self) -> bool:
        return bool(self.constraints().get("escalation_requires_second_person", True))

    def blocking_acceptability_hints(self) -> List[str]:
        block = self.constraints().get("block_accept_if", {})
        return [str(x) for x in block.get("acceptability_hint_in", [])]

    def hard_accept_block_category(self) -> Optional[str]:
        value = self.raw["thresholds"].get("hard_accept_block_category")
        return str(value) if value else None

    # --------------------------------------------------------------- authority

    def authority_roles(self) -> List[str]:
        return [str(r["role"]) for r in self.raw.get("escalation", {}).get("authority_matrix", [])]

    def max_category_to_accept(self, role: str) -> Optional[str]:
        for row in self.raw.get("escalation", {}).get("authority_matrix", []):
            if str(row["role"]) == role:
                return str(row["max_category_to_accept"])
        return None

    def can_accept(self, role: str, category: str) -> bool:
        hard_block = self.hard_accept_block_category()
        if hard_block and self.category_rank(category) >= self.category_rank(hard_block):
            return False
        ceiling = self.max_category_to_accept(role)
        if ceiling is None:
            return False
        return self.category_rank(category) <= self.category_rank(ceiling)

    def roles_that_can_accept(self, category: str) -> List[str]:
        return [r for r in self.authority_roles() if self.can_accept(r, category)]

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

    points: Dict[str, List[int]] = {}
    for dimension in ("likelihood", "impact"):
        scale = raw["scales"].get(dimension)
        if not scale:
            raise ValueError(f"Missing scale: {dimension}")
        if "labels" not in scale:
            raise ValueError(f"Missing labels for: {dimension}")
        if "normalisation" not in scale:
            raise ValueError(f"Missing normalisation for: {dimension}")

        vmin, vmax = int(scale["normalisation"]["min"]), int(scale["normalisation"]["max"])
        if vmin >= vmax:
            raise ValueError(f"Invalid bounds for {dimension}: require min < max")

        expected = set(range(vmin, vmax + 1))
        labelled = {int(k) for k in scale["labels"]}
        if labelled != expected:
            raise ValueError(
                f"Labels for {dimension} must cover every point from {vmin} to {vmax}. "
                f"Missing: {sorted(expected - labelled)}. Unexpected: {sorted(labelled - expected)}."
            )
        points[dimension] = sorted(expected)

    cats = raw["thresholds"].get("categories")
    if not isinstance(cats, list) or not cats:
        raise ValueError("Threshold categories invalid")
    names = [str(c["name"]) for c in cats]

    if float(cats[0]["min"]) > 0.0:
        raise ValueError("Threshold categories must start at 0.0")
    for previous, nxt in zip(cats, cats[1:]):
        if float(previous["max"]) != float(nxt["min"]):
            raise ValueError(
                f"Threshold categories leave a gap between {previous['name']} and {nxt['name']}"
            )
    if float(cats[-1]["max"]) <= 1.0:
        raise ValueError("Threshold categories must cover a score of 1.0")

    _validate_scoring(raw, points, names)
    _validate_decisions(raw, names)
    _validate_governance(raw, names)


def _validate_scoring(raw: Dict[str, Any], points: Dict[str, List[int]], names: List[str]) -> None:
    scoring = raw["scoring"]
    if scoring.get("method") != "matrix":
        raise ValueError("Unsupported scoring method")

    matrix = scoring.get("category_matrix") or {}
    cells = matrix.get("cells")
    if not isinstance(cells, dict):
        raise ValueError("Missing scoring.category_matrix.cells")

    rows = {int(k) for k in cells}
    if rows != set(points["likelihood"]):
        raise ValueError("The category matrix must have one row per likelihood point")

    grid: List[List[int]] = []
    for likelihood in points["likelihood"]:
        row = cells[str(likelihood)]
        if not isinstance(row, list) or len(row) != len(points["impact"]):
            raise ValueError(f"Matrix row {likelihood} must have one cell per impact point")
        unknown = [c for c in row if c not in names]
        if unknown:
            raise ValueError(f"Matrix row {likelihood} uses unknown categories: {unknown}")
        grid.append([names.index(c) for c in row])

    # A matrix that dips as likelihood or impact rises is a governance error,
    # not a preference. Catch it on load rather than in a review meeting.
    for r, row in enumerate(grid):
        for c in range(len(row) - 1):
            if row[c] > row[c + 1]:
                raise ValueError(
                    f"Matrix is not monotonic across impact at likelihood {points['likelihood'][r]}"
                )
    for c in range(len(grid[0])):
        for r in range(len(grid) - 1):
            if grid[r][c] > grid[r + 1][c]:
                raise ValueError(
                    f"Matrix is not monotonic across likelihood at impact {points['impact'][c]}"
                )

    ordering = scoring.get("ordering_score") or {}
    if ordering.get("method") != "ordinal_product":
        raise ValueError("Unsupported ordering score method")
    if "rounding" not in ordering:
        raise ValueError("Missing ordering_score rounding")


def _validate_decisions(raw: Dict[str, Any], names: List[str]) -> None:
    mapping = raw["decision_policy"].get("by_category")
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("Missing decision_policy.by_category")
    for name in names:
        if name not in mapping:
            raise ValueError(f"No decision mapped for category: {name}")
        try:
            DecisionType(str(mapping[name]).upper())
        except ValueError as exc:
            raise ValueError(f"Unknown decision for category {name}: {mapping[name]}") from exc

    for name, rule in dict(raw.get("overrides", {})).items():
        floor = rule.get("floor_category")
        if floor is not None and floor not in names:
            raise ValueError(f"Override {name} floors to an unknown category: {floor}")


def _validate_governance(raw: Dict[str, Any], names: List[str]) -> None:
    hard_block = raw["thresholds"].get("hard_accept_block_category")
    if hard_block is not None and str(hard_block) not in names:
        raise ValueError(f"Unknown hard_accept_block_category: {hard_block}")

    escalation = raw.get("escalation", {})
    for name in escalation.get("require_approval_if", {}).get("category_in", []):
        if str(name) not in names:
            raise ValueError(f"Escalation references an unknown category: {name}")

    matrix = escalation.get("authority_matrix", [])
    if not matrix:
        raise ValueError("Missing escalation.authority_matrix")
    seen: set[str] = set()
    for row in matrix:
        role = str(row["role"])
        if role in seen:
            raise ValueError(f"Duplicate authority role: {role}")
        seen.add(role)
        ceiling = str(row["max_category_to_accept"])
        if ceiling not in names:
            raise ValueError(f"Role {role} may accept an unknown category: {ceiling}")
        if hard_block and names.index(ceiling) >= names.index(str(hard_block)):
            raise ValueError(
                f"Role {role} may accept {ceiling}, which the hard block forbids"
            )
