from __future__ import annotations

from typing import Any, Dict, List


class BasicExplainability:
    def explain(
        self,
        classifications: Dict[str, Dict[str, Any]],
        indicator_details: Dict[str, Dict[str, Any]],
        local_scores: Dict[str, float],
        top_n: int = 5,
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        contributors_by_domain: Dict[str, List[Dict[str, Any]]] = {}

        for indicator_id, meta in indicator_details.items():
            domain = str(meta.get("domain", ""))
            if not domain:
                continue

            score = float(local_scores.get(indicator_id, 0.0))
            entry = {
                "indicator_id": indicator_id,
                "score": score,
                "category": meta.get("category"),
            }

            contributors_by_domain.setdefault(domain, []).append(entry)

        for domain, entries in contributors_by_domain.items():
            entries.sort(key=lambda x: abs(float(x.get("score", 0.0))), reverse=True)
            contributors_by_domain[domain] = entries[:top_n]

        return {
            "top_contributors_by_domain": contributors_by_domain
        }
