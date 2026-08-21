# risk-decision

A reproducible, auditable and explainable risk-based decision framework.

Two entry points share this repo:

- **Risk Decision Wizard** (`streamlit_app.py`, `core/`). Guided single-case assessment. Likelihood and impact are scored under a versioned policy, then locked with an audit trail.
- **Decision engine** (`src/risk_decision/`). Batch component pipeline for indicator-level input: scorer, aggregator, classifier, rules, explainability, audit.

The two do not share a scoring model. The wizard scores one risk on a 0 to 1 scale; the engine aggregates indicator scores per domain. Keep that distinction in mind when reading the code.

## Quick start

```bash
pip install -r requirements.txt

./run.sh                                   # wizard
python -m risk_decision.cli.main input.json  # batch engine
pytest                                     # 27 tests
```

## Where the rules live

Behaviour sits in config, not in code:

- `config/policy_config.json` scales, normalisation, thresholds, decision mapping, overrides, escalation
- `config/question_bank.json` every wizard question, its step, its validation and its option source

Question options resolve against the model enums and the policy scales at load time, so a question referencing something that no longer exists fails immediately rather than at validation.

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
│   └── usage_guide.md
│
├── core/                       wizard: policy driven single-case assessment
│   ├── models.py               pydantic schema and enums
│   ├── policy.py               config loader, normalisation, thresholds
│   ├── questions.py            question bank loader
│   ├── engine.py               evaluation and override rules
│   ├── wizard.py               step machine and validation
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

An evaluation snapshot is immutable once written:

```json
{
  "created_at": "...",
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

`inputs_hash` is SHA-256 over the assessed inputs only. Derived values are excluded, so the same inputs always produce the same hash.

## Not implemented yet

- Risk controls and residual risk after mitigation
- A register view ranking multiple cases against each other
- Automated risk identification from a library

The wizard assesses one risk that you have already identified. It does not find risks for you.
