# risk-decision

A reproducible, auditable and explainable risk-based decision framework.

Two entry points share this repo:

- **Risk Decision Wizard** (`streamlit_app.py`, `core/`). Guided single-case assessment. Likelihood and impact are scored under a versioned policy, then locked with an audit trail.
- **Decision engine** (`src/risk_decision/`). Batch component pipeline for indicator-level input: scorer, aggregator, classifier, rules, explainability, audit.

The two do not share a scoring model. The wizard scores one risk on a 0 to 1 scale; the engine aggregates indicator scores per domain and classifies them against absolute thresholds. Keep that distinction in mind when reading the code.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

./run.sh                                     # wizard
python -m risk_decision.cli.main input.example.json  # batch engine
pytest                                       # 34 tests
```

The wizard writes case data to `data/` in the working directory. That path is gitignored.

## Where the rules live

Behaviour sits in config, not in code:

- `config/policy_config.json` scales, normalisation, thresholds, category overrides, decision mapping, escalation
- `config/question_bank.json` every wizard question, its step, its validation and its option source

Question options resolve against the model enums and the policy scales at load time. A question referencing an enum, a policy scale, a step or a path that no longer exists raises on load, not at validation. Policy load applies the same rule to itself: labels must cover every point between min and max, categories must be contiguous and cover 1.0, and every category must map to a decision.

Changing behaviour means editing config and incrementing `policy_version`. See `docs/policy_engine.md`.

## Repository layout

```text
risk-decision/
├── README.md
├── run.sh
├── streamlit_app.py            wizard entry point
├── pyproject.toml
├── requirements.txt
│
├── config/
│   ├── policy_config.json
│   └── question_bank.json
│
├── docs/
│   ├── policy_engine.md
│   ├── policy_engine_v1.md     superseded, kept for reference
│   └── usage_guide.md
│
├── core/                       wizard: policy driven single-case assessment
│   ├── models.py               pydantic schema and enums
│   ├── policy.py               config loader, normalisation, thresholds
│   ├── questions.py            question bank loader and answer validation rules
│   ├── engine.py               evaluation, overrides, input hashing
│   ├── wizard.py               step machine, validation, locking
│   ├── storage.py              drafts, snapshots, decisions, audit log
│   └── utils.py
│
├── src/risk_decision/          batch component engine
│   ├── core/                   decision_engine, decision_types, fingerprints
│   ├── engine/                 scorer, aggregator, classifier, rules,
│   │                           explainability, audit_trail
│   ├── domain/                 domains, categories, indicators, activities
│   ├── io/                     loaders, exporters
│   ├── cli/                    batch entry point
│   └── ui/                     engine Streamlit view
│
├── tests/
└── data/                       runtime case data, gitignored
```

## Data model

An evaluation snapshot is immutable once written. Revising a case means a new version, not a recomputed snapshot:

```json
{
  "created_at": "2026-08-23T12:00:00+00:00",
  "policy_version": "v1.1",
  "likelihood_normalised": 0.75,
  "impact_normalised": 0.75,
  "overall_risk_score": 0.5625,
  "risk_category": "high",
  "recommended_decision": "REDUCE",
  "escalation_required": true,
  "applied_overrides": [],
  "inputs_hash": "..."
}
```

`inputs_hash` is SHA-256 over the assessed inputs only. Derived values are excluded by construction in `core/engine.py`, so the same inputs always produce the same hash.

Models reject unknown fields. A field the schema does not know about raises rather than being dropped, which is what previously let a recorded override reason disappear.

## Overrides

Score alone can classify a severe risk as low. Two overrides in `config/policy_config.json` prevent that, and a third flags personal data:

| Override | Fires when | Effect |
| --- | --- | --- |
| `catastrophic_impact` | impact level 5 | category floored to high |
| `irreversible_impact` | reversibility is Irreversible | category floored to medium |
| `privacy_signal` | configured keywords appear in the event, consequences or worst credible outcome | escalation only |

Overrides can raise a category, never lower it. Every one that fires is named in `applied_overrides` and explained in the case feedback.

## Not implemented yet

- Risk controls and residual risk after mitigation
- A register view ranking multiple cases against each other
- Automated risk identification from a library

The wizard assesses one risk that you have already identified. It does not find risks for you.
