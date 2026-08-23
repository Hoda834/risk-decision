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
pytest                                       # 59 tests
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

## How a risk is categorised

Likelihood and impact are ordinal labels, so the framework does not multiply them. The category is read from an explicit cell in `config/policy_config.json`:

```
L\I        1          2          3          4          5
 1        low        low        low        medium     high
 2        low        low        medium     medium     high
 3        low        medium     medium     high       critical
 4        low        medium     high       high       critical
 5        medium     medium     high       critical   critical
```

Every cell is a stated position that can be reviewed on its own. Load fails if the grid is not monotonic, so a category can never fall as likelihood or impact rises.

A separate ordering score, `(likelihood * impact - 1) / 24`, sorts cases. It does not classify them, and the UI labels it as an ordering value.

## Governance

The policy is enforced, not just described:

- **Authority.** Each role has a category ceiling for acceptance: risk owner up to low, security lead up to medium, management and executive sponsor up to high. No role may accept a critical risk. Load fails if the matrix grants a role more than the hard block allows.
- **Blocked acceptance.** An outcome the assessor marked "Not acceptable" cannot be accepted at any level.
- **Escalation.** Triggered by a high or critical category, by any override, or by confidence of 2 or below. Every trigger records its reason on the snapshot.
- **Second person.** An escalated case needs an approver, and the approver cannot be the person recording the decision.
- **Review date.** Required, and defaulted from the time to impact.
- **Integrity.** The inputs hash is verified on load, a locked version refuses a write that would change its assessed inputs, and the audit log is hash-chained so an edited or removed entry breaks the chain.

## Data model

An evaluation snapshot is immutable once written. Revising a case means a new version, not a recomputed snapshot:

```json
{
  "created_at": "2026-08-23T12:00:00+00:00",
  "policy_version": "v1.2",
  "likelihood_normalised": 0.75,
  "impact_normalised": 0.75,
  "overall_risk_score": 0.625,
  "matrix_category": "high",
  "risk_category": "high",
  "recommended_decision": "REDUCE",
  "escalation_required": true,
  "escalation_reasons": ["Category is high."],
  "applied_overrides": [],
  "accept_blockers": [],
  "roles_that_may_accept": ["management", "executive_sponsor"],
  "inputs_hash": "..."
}
```

`inputs_hash` is SHA-256 over the assessed inputs only. Derived values are excluded by construction in `core/engine.py`, so the same inputs always produce the same hash.

Models reject unknown fields. A field the schema does not know about raises rather than being dropped, which is what previously let a recorded override reason disappear.

## Overrides

Three overrides sit on top of the matrix:

| Override | Fires when | Effect |
| --- | --- | --- |
| `catastrophic_impact` | impact level 5 | category floored to high, escalation |
| `irreversible_impact` | reversibility is Irreversible | category floored to medium, escalation |
| `privacy_signal` | configured keywords appear in the event, consequences or worst credible outcome | escalation only |

Overrides can raise a category, never lower it. Every one that fires is named in `applied_overrides` and explained in the case feedback.

## Not implemented yet

- Risk controls and residual risk after mitigation, so a case can be decided but not closed
- Benefit-risk analysis
- A register view ranking multiple cases against each other, and duplicate detection between cases
- Frequency anchors on the likelihood labels, and per-domain severity descriptors
- Automated risk identification from a library. The taxonomy in `src/risk_decision/domain/` is not yet wired into the wizard
- Upside risk. `anchor.direction` is recorded, but the decision vocabulary is downside only

The wizard assesses one risk that you have already identified. It does not find risks for you.
