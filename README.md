# risk-decision
A reproducible, auditable, and explainable risk-based decision framework
A reproducible, auditable, and explainable risk-based decision framework.

```
## Repository layout

```text
risk-decision/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── run.sh
├── streamlit_app.py
│
├── docs/
│   ├── architecture.md
│   ├── policy_engine_v1.md
│   ├── decision_logic.md
│   └── audit_traceability.md
│
├── data/
│   └── examples/
│
├── config/
│
├── src/
│   └── risk_decision/
│       ├── __init__.py
│       │
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py
│       │
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── activities.py
│       │   ├── categories.py
│       │   ├── domains.py
│       │   ├── indicators.py
│       │   └── schemas.py
│       │
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── scorer.py
│       │   ├── aggregator.py
│       │   ├── classifier.py
│       │   ├── rules.py
│       │   ├── explainability.py
│       │   └── audit_trail.py
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── decision_engine.py
│       │   ├── decision_types.py
│       │   └── fingerprints.py
│       │
│       ├── modules/
│       │   └── asset_risk/
│       │       ├── __init__.py
│       │       ├── models.py
│       │       ├── scoring.py
│       │       └── readiness.py
│       │
│       ├── io/
│       │   ├── __init__.py
│       │   ├── loaders.py
│       │   └── exporters.py
│       │
│       └── ui/
│           ├── __init__.py
│           └── streamlit_app.py
│
└── tests/
    ├── test_decision_engine.py
    ├── test_policy_classifier.py
    ├── test_rules.py
    └── test_audit_fingerprints.py

```

## Test configuration

`pyproject.toml` configures pytest with `pythonpath = ["src"]`, so tests can import the package from the `src/` layout without extra environment setup.
