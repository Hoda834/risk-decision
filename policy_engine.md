# Risk Decision Wizard, Policy Engine v1.1

## 1. Purpose

This document defines the deterministic policy layer used by the Risk Decision Wizard.

The policy layer specifies how raw inputs become scores, how scores are normalised and aggregated, how categories are assigned, and how decisions are derived.

Every rule below is held in `config/policy_config.json` and read at runtime. The document describes the config, it does not duplicate it. Changing behaviour means changing the config and incrementing `policy_version`.

## 2. Core model

Two dimensions are assessed: likelihood and impact. Each carries a raw score, a confidence value and contextual metadata.

Confidence is stored for traceability but does not alter aggregation. Interpretability is prioritised over statistical dampening.

## 3. Scales

Both scales are ordinal, 1 to 5, and every point carries a label.

Likelihood: 1 rare, 2 unlikely, 3 possible, 4 likely, 5 almost certain.

Impact: 1 minimal, 2 minor, 3 moderate, 4 major, 5 catastrophic.

The bounds in `scales.<dimension>.normalisation` are the single source of truth. The UI builds its sliders from them, so a scale change propagates without code edits. Policy load fails if the labels do not cover every point between min and max.

## 4. Normalisation

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

Impact severity applies uniformly across selected domains. No domain weighting is applied.

## 5. Aggregation

```
overall_risk_score = round(likelihood_normalised * impact_normalised, decimals)
```

Range 0.00 to 1.00. Both dimensions must be elevated for the score to be elevated. High impact alone or high likelihood alone does not produce a high score.

Multiplication has one known consequence: a likelihood of 1 drives the score to zero regardless of impact. Section 7 handles that case explicitly rather than leaving it to the reader.

## 6. Categories and decisions

```
0.00 <= score < 0.20   low        ACCEPT
0.20 <= score < 0.50   medium     REDUCE
0.50 <= score < 0.80   high       REDUCE
0.80 <= score <= 1.00  critical   AVOID
```

Decisions use the same vocabulary as `DecisionType` in `core/models.py`: ACCEPT, REDUCE, TRANSFER, AVOID, DEFER. No other decision words appear anywhere in the system.

Category bands must be contiguous and cover the full range. Policy load fails otherwise, so a gap cannot reach production silently.

## 7. Overrides

Overrides raise a result. They never lower one.

**Catastrophic impact.** Impact of 5 forces a minimum category of high and a minimum decision of REDUCE, whatever the likelihood. A rare event with a catastrophic worst credible outcome is not a low risk.

**Irreversible consequences.** Reversibility of "Irreversible" forces a minimum category of medium. Irreversibility removes the option of correcting the outcome later, so it cannot be classified as low.

Applied overrides are listed in `applied_overrides` on the snapshot and named in the rationale.

## 8. Escalation

Escalation is required when the score reaches `escalation.require_approval_if.score_gte`, or when any override is applied.

The authority matrix caps what each role may accept:

```
risk_owner      up to 0.2
security_lead   up to 0.5
management      up to 0.7
```

## 9. Design constraints

The engine deliberately avoids hidden weighting, domain weighting, confidence scaling, probabilistic modelling and dynamic thresholds. Transparency and reproducibility come first.

## 10. Known limitations

No Bayesian updating, no longitudinal calibration, no domain-specific weighting, no machine learning adjustment, no historical tuning. All excluded on purpose.

Also absent, and planned rather than excluded: risk controls, residual risk after mitigation, and a register view across multiple cases.

## 11. Versioning and governance

Every snapshot stores `policy_version`, `created_at` and `inputs_hash`.

`inputs_hash` is a SHA-256 hash of the assessed inputs only. Derived values are excluded, so the hash answers "what was assessed", not "what was computed".

Any change to normalisation, aggregation, thresholds, decision mapping or overrides requires a policy version increment. Outputs from different policy versions are not directly comparable.

## 12. Interpretation

The score is a structured representation of judgement. It is not a probabilistic forecast, not a compliance guarantee and not a financial prediction. The engine supports structured reasoning. It does not replace domain expertise.
