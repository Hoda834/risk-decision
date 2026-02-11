# Risk Decision Wizard – Usage Guide

## 1. Overview

The Risk Decision Wizard is a structured decision engine designed to:

- force explicit risk definition
- reduce ambiguity in scoring
- make decision logic transparent
- separate policy from judgement

The system guides the user through sequential stages.

---

## 2. Step-by-Step Workflow

### Step 1: Anchor

Define the framing context.

Required:

- Case name
- Owner
- Anchor type (Problem or Opportunity)
- Value statement
- Direction

Purpose:

Risk without a defined objective or value anchor is meaningless.

---

### Step 2: Definition

Define the risk structure.

Required fields:

- Event
- Triggers
- Cause categories
- Vulnerability
- Consequences
- Time to impact
- Scope
- Assumptions
- Data used
- References

Purpose:

Force boundary clarity before numerical scoring.

---

### Step 3: Likelihood

Define probability.

Inputs:

- Basis
- Signals
- Raw likelihood (1–5)
- Confidence (1–5)

Interpretation:

1 → Rare  
5 → Almost certain  

Confidence captures epistemic uncertainty but does not scale score in v1.

---

### Step 4: Impact

Define severity.

Inputs:

- Impact domains
- Worst credible outcome
- Reversibility
- Impact severity (1–5)
- Confidence (1–5)
- Acceptability hint

Interpretation:

1 → Minimal  
5 → Catastrophic  

---

### Step 5: Review

System compiles structured JSON snapshot.

User must review:

- Raw inputs
- Derived normalised values
- Overall risk score
- Category
- Decision type

This stage ensures traceability before finalisation.

---

### Step 6: Finalisation

System outputs:

- overall_risk_score
- risk_category
- decision_type
- rationale
- policy_version
- input_hash

Snapshot is immutable.

Any modification requires new version.

---

## 3. Interpretation of Results

Overall risk score is not a prediction.

It is:

- a structured representation of judgement
- anchored to explicit definitions
- reproducible under defined policy rules

Decision outputs are guidance, not mandates.

---

## 4. Good Practice Recommendations

- Do not skip definition fields.
- Avoid scoring before boundary clarity.
- Record real assumptions.
- Avoid artificially inflating confidence.
- Document overrides explicitly.

---

## 5. When Not to Use

Do not use this system:

- for probabilistic forecasting
- for financial modelling
- for automated compliance documentation
- as a substitute for domain expertise

It is a structured reasoning aid, not an oracle.

---

## 6. Governance

Policy changes must be:

- versioned
- documented
- justified

Evaluation results must always store policy_version.
