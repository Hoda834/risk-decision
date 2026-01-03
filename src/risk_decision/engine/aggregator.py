from __future__ import annotations

from typing import Any, Dict


class BasicAggregator:
    def aggregate(
        self,
        indicator_details: Dict[str, Any],
        local_scores: Dict[str, float],
    ) -> Dict[str, Any]:
        domain_sum: Dict[str, float] = {}
        domain_count: Dict[str, int] = {}

        category_sum: Dict[str, float] = {}
        category_count: Dict[str, int] = {}

        for indicator_id, meta in indicator_details.items():
            score = float(local_scores.get(indicator_id, 0.0))
            domain = str(meta.get("domain", ""))
            category = str(meta.get("category", ""))

            if domain:
                domain_sum[domain] = domain_sum.get(domain, 0.0) + score
                domain_count[domain] = domain_count.get(domain, 0) + 1

            if category:
                category_sum[category] = category_sum.get(category, 0.0) + score
                category_count[category] = category_count.get(category, 0) + 1

        domain_scores = {
            d: domain_sum[d] / max(1, domain_count.get(d, 1))
            for d in domain_sum
        }

        category_scores = {
            c: category_sum[c] / max(1, category_count.get(c, 1))
            for c in category_sum
        }

        return {
            "domain_scores": domain_scores,
            "category_scores": category_scores,
        }

