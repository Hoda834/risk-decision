# Risk Decision Wizard, usage guide

## 1. Overview

The wizard forces explicit risk definition before scoring, keeps the scoring rules in config rather than in code, and records what was assessed so the result can be reproduced.

Install with `pip install -e ".[dev]"`, then run it with `./run.sh`, or `streamlit run streamlit_app.py`. Case data is written to `data/` in the working directory.

Cases are written to `data/` in the repo root. That directory is gitignored.

## 2. Workflow

### Step 1, anchor

Case name, owner, anchor type, value statement, direction.

Risk without a defined objective or value anchor is meaningless.

### Step 2, definition

Event, triggers, cause categories, vulnerability, consequences, time to impact, scope, assumptions, data used, references.

Boundary clarity before numerical scoring.

### Step 3, likelihood

Basis, signals, likelihood 1 to 5, confidence 1 to 5.

The scale labels come from `config/policy_config.json`. Confidence is recorded for traceability and does not scale the result.

### Step 4, impact

Domains, worst credible outcome, reversibility, severity 1 to 5, confidence 1 to 5, acceptability hint.

### Step 5, review

The wizard lists any incomplete step and blocks evaluation until they are resolved. The full draft is shown as JSON before you commit to it.

### Step 6, evaluate and lock

The version is locked and three artefacts are written:

```
data/drafts/<case_id>/v<n>.json      the inputs
data/snapshots/<case_id>/v<n>.json   the evaluation
data/decisions/<case_id>/v<n>.json   the decision
data/cases/<case_id>/audit.log.jsonl the event trail
```

A locked version is never recomputed. To change anything, use "Revise as a new version", which increments the version and clears the snapshot.

## 3. Overriding the recommendation

The policy recommendation is the default decision. Choosing anything else requires a written reason, and the record stores `follows_recommendation: false` alongside your note.

## 4. Reading the result

The score is a structured representation of judgement, not a prediction.

Two override rules can raise a result above what the arithmetic gives. A catastrophic impact cannot be classified below high. Irreversible consequences cannot be classified as low. When either applies, the reason appears in the rationale.

## 5. Good practice

Do not skip definition fields. Do not score before boundary clarity. Record real assumptions. Do not inflate confidence. Document every override.

## 6. When not to use it

Not for probabilistic forecasting, financial modelling, automated compliance documentation, or as a substitute for domain expertise.

It is a structured reasoning aid, not an oracle.

## 7. Governance

Policy changes must be versioned, documented and justified. Every evaluation stores the policy version that produced it.
