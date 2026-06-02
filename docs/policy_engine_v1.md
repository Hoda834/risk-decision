# Risk Decision Wizard – Policy Engine v1

## 1. Purpose

This document defines the deterministic policy layer used by the Risk Decision Wizard.

The policy layer specifies:

- how raw inputs are transformed into scores  
- how scores are normalised  
- how aggregated risk is computed  
- how risk categories are assigned  
- how decisions are derived  

All outputs are deterministic under this policy version.

---

## 2. Core Model

The system evaluates risk using two primary dimensions:

- Likelihood  
- Impact  

Each dimension includes:

- Raw score (1–5)
- Confidence (1–5)
- Contextual metadata

Confidence is stored for traceability but does not alter numerical aggregation in v1.

---

## 3. Likelihood Policy

### 3.1 Inputs

- Raw likelihood value (1–5)
- Confidence (1–5)
- Basis
- Signals

### 3.2 Normalisation Formula


Mapping:

1 → 0.00  
5 → 1.00  

Confidence is not applied to scaling in v1.

Rationale:  
Interpretability and auditability are prioritised over statistical dampening.

---

## 4. Impact Policy

### 4.1 Inputs

- Impact domains
- Worst credible outcome
- Reversibility
- Raw severity (1–5)
- Confidence (1–5)
- Acceptability hint

### 4.2 Normalisation Formula


If multiple domains are selected, severity applies uniformly in v1.

No domain weighting is applied.

---

## 5. Aggregation Rule

Overall risk score is calculated as:


Range:

0.00 to 1.00

Properties:

- If either dimension is zero, overall risk is zero.
- High impact alone does not produce high risk.
- High likelihood alone does not produce high risk.

Both must be elevated.

Confidence does not modify aggregation in v1.

---

## 6. Risk Category Mapping

Categories are derived from overall risk score:


Thresholds are fixed in v1.

---

## 7. Decision Mapping

Decision type is derived from risk category.

Baseline mapping:

Low       → ACCEPT  
Medium    → REDUCE  
High      → REDUCE or MITIGATE  
Critical  → STOP or ESCALATE  

In v1:

- Medium maps to REDUCE by default.
- Decision output is deterministic.
- Human override must be documented explicitly.

---

## 8. Design Constraints

The v1 engine intentionally:

- avoids hidden weighting
- avoids domain weighting
- excludes confidence scaling
- avoids probabilistic modelling
- avoids dynamic thresholds

Reason:

Transparency, reproducibility, and interpretability are prioritised.

---

## 9. Known Limitations

- No Bayesian updating
- No longitudinal calibration
- No domain-specific weighting
- No machine learning adjustment
- No historical tuning

These are intentionally excluded from v1.

---

## 10. Versioning and Governance

Each evaluation snapshot stores:

- policy_version
- timestamp
- input_hash

Any change to:

- normalisation formulas
- aggregation rule
- category thresholds
- decision mapping logic

requires policy version increment.

Outputs generated under different policy versions are not directly comparable.

---

## 11. Interpretation Warning

Overall risk score is:

- a structured judgement representation  
- not a probabilistic forecast  
- not a compliance guarantee  
- not a financial prediction  

The engine supports structured reasoning.  
It does not replace domain expertise.
