# Risk Decision Wizard, Policy Engine v1.2

## 1. Purpose

This document defines the deterministic policy layer used by the Risk Decision Wizard.

The policy layer specifies how raw inputs become scores, how scores are normalised and aggregated, how categories are assigned, and how decisions are derived.

Every rule below is held in `config/policy_config.json` and read at runtime. The document describes the config, it does not duplicate it. Changing behaviour means changing the config and incrementing `policy_version`.

## 2. Core model

Two dimensions are assessed: likelihood and impact. Each carries a raw score, a confidence value and contextual metadata.

Confidence does not alter the category. Interpretability is prioritised over statistical dampening. It does alter the review path: confidence of 2 or below forces escalation, per section 8.

## 3. Scales

Both scales are ordinal, 1 to 5, and every point carries a label.

Likelihood: 1 rare, 2 unlikely, 3 possible, 4 likely, 5 almost certain.

Impact: 1 minimal, 2 minor, 3 moderate, 4 major, 5 catastrophic.

The labels carry no frequency or severity anchor yet. Two assessors will not converge until they do. Adding a rate to each likelihood point, per test or per instrument-year, and a domain-specific descriptor to each impact point is the next change to this document.

The bounds in `scales.<dimension>.normalisation` are the single source of truth. The UI builds its sliders from them, so a scale change propagates without code edits. Policy load fails if the labels do not cover every point between min and max.

## 4. Normalisation

Normalisation no longer drives the category, which comes from the matrix in section 6. The normalised values are retained on the snapshot for reporting and for comparison across policy versions.

Both dimensions use min-max normalisation:

```
normalised = (raw - min) / (max - min)
```

With min 1 and max 5:

```
1 -> 0.00
2 -> 0.25
3 -> 0.50
4 -> 0.75
5 -> 1.00
```

Values outside the range are clamped to 0.0 and 1.0.

Impact severity applies uniformly across selected domains. No domain weighting is applied, so one severity value covers a case tagged both Safety and Financial. Per-domain severity descriptors, with the maximum taken across the selected domains, is a known gap.

## 5. Aggregation

Likelihood and impact are ordinal. The distance between "possible" and "likely" is not defined, so multiplying the two points produces a number whose ordering is an artefact of the normalisation rather than a property of the risk. Policy v1.1 did exactly that, and 9 of its 25 cells scored zero because a 1 on either axis wiped out the other.

v1.2 does not aggregate. The category is read from an explicit cell:

```
category = scoring.category_matrix.cells[likelihood][impact]
```

Every cell is a stated governance position, reviewable on its own terms.

A separate ordering score is kept for sorting cases within and across categories:

```
overall_risk_score = (likelihood * impact - 1) / 24
```

It orders. It does not classify. The snapshot records both, and the UI labels the score as an ordering value so it is not read as a severity.

## 6. Categories and decisions

The matrix in `config/policy_config.json`:

```
L\I        1          2          3          4          5
 1        low        low        low        medium     high
 2        low        low        medium     medium     high
 3        low        medium     medium     high       critical
 4        low        medium     high       high       critical
 5        medium     medium     high       critical   critical
```

Decisions map from the category:

```
low        ACCEPT
medium     REDUCE
high       REDUCE
critical   AVOID
```

Two properties are enforced on load, so a bad edit cannot reach production:

- Every cell names a category in the vocabulary, and every likelihood point has a row.
- The grid is monotonic. Category never falls as likelihood or impact rises. A dip is a governance error, not a preference.

Impact 4 has a floor of medium and impact 5 a floor of high, visible in the columns. That is the deliberate correction to v1.1, where an unlikely major impact returned ACCEPT.

Decisions use the same vocabulary as `DecisionType` in `core/models.py`: ACCEPT, REDUCE, TRANSFER, AVOID, DEFER. No other decision words appear anywhere in the system.

## 7. Overrides

Overrides raise a result. They never lower one.

**Catastrophic impact.** Impact of 5 forces a minimum category of high, whatever the likelihood. The matrix already holds column 5 at high or above, so this override changes nothing on its own. It is kept because it also triggers escalation and it names itself in the record, and because it keeps the rule stated rather than implicit in a grid someone may later edit.

**Irreversible consequences.** Reversibility of "Irreversible" forces a minimum category of medium. Irreversibility removes the option of correcting the outcome later, so it cannot be classified as low.

**Privacy signal.** Configured keywords appearing in the event, the consequences or the worst credible outcome flag the case for approval. This one does not move the category. It only sets `escalation_required`, because a personal data question is an approval question rather than a severity question.

Applied overrides are listed in `applied_overrides` on the snapshot and named in the case feedback.

## 8. Escalation and authority

Escalation is required when any of these hold, and the reason is recorded on the snapshot:

- The category is high or critical.
- Any override fired.
- Confidence is 2 or below on either dimension. A weak evidence base does not lower the risk, it widens it, so it changes the review path and not the category.

The authority matrix caps what each role may accept, by category rather than by score:

```
risk_owner          up to low
security_lead       up to medium
management          up to high
executive_sponsor   up to high
```

`thresholds.hard_accept_block_category` is critical, so no role may accept a critical risk. Load fails if the matrix grants a role more than the hard block allows.

Acceptance is also blocked, at any level, when the assessor recorded the outcome as "Not acceptable". Asking the question and then ignoring the answer would be worse than not asking.

An escalated case needs a second person. The approver and the person recording the decision must be different, and an ACCEPT decision needs a review date.

## 9. Design constraints

The engine deliberately avoids hidden weighting, domain weighting, confidence scaling, probabilistic modelling and dynamic thresholds. Transparency and reproducibility come first.

## 10. Known limitations

No Bayesian updating, no longitudinal calibration, no domain-specific weighting, no machine learning adjustment, no historical tuning. All excluded on purpose.

Also absent, and planned rather than excluded: risk controls, residual risk after mitigation, benefit-risk analysis, a register view across multiple cases, and frequency anchors on the scale labels.

The wizard covers identification, analysis, evaluation and a decision. It does not cover treatment. A case can be decided but not closed.

## 11. Versioning and governance

Every snapshot stores `policy_version`, `created_at` and `inputs_hash`.

`inputs_hash` is a SHA-256 hash of the assessed inputs only. Derived values are excluded, so the hash answers "what was assessed", not "what was computed". It is verified on load. A locked version refuses a write that would change its assessed inputs, so revising means a new version.

The audit log is hash-chained. Each entry carries the hash of the one before it, so an edited or removed line breaks the chain rather than passing unnoticed.

Any change to normalisation, aggregation, thresholds, decision mapping or overrides requires a policy version increment. Outputs from different policy versions are not directly comparable.

## 12. Interpretation

The score is a structured representation of judgement. It is not a probabilistic forecast, not a compliance guarantee and not a financial prediction. The engine supports structured reasoning. It does not replace domain expertise.
