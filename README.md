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
├── docs/
│   ├── architecture.md
│   ├── decision_logic.md
│   └── audit_traceability.md
├── data/
│   └── examples/
├── run.sh
├── streamlit_app.py
├── config/
├── core/
├── src/
│   └── risk_decision/
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── decision_engine.py
│       │   ├── decision_types.py
│       │   └── fingerprints.py
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── activities.py
│       │   ├── domains.py
│       │   ├── categories.py
│       │   ├── domains.py
│       │   ├── indicators.py
│       │   └── schemas.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── decision_types.py
│       │   ├── decision_engine.py
│       │   └── fingerprints.py
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── scorer.py
│       │   ├── aggregator.py
│       │   ├── audit_trail.py
│       │   ├── classifier.py
│       │   ├── rules.py
│       │   ├── explainability.py
│       │   └── audit_trail.py
│       ├── modules/
│       │   └── asset_risk/
│       │       ├── __init__.py
│       │       ├── models.py
│       │       ├── scoring.py
│       │       └── readiness.py
│       │   ├── rules.py
│       │   └── scorer.py
│       ├── io/
│       │   ├── __init__.py
│       │   ├── loaders.py
│       │   └── exporters.py
│       └── cli/
│       │   ├── exporters.py
│       │   └── loaders.py
│       ├── modules/
│       │   └── __init__.py
│       └── ui/
│           ├── __init__.py
│           └── main.py
│           └── streamlit_app.py
└── tests/
    ├── test_audit_fingerprints.py
    ├── test_decision_engine.py
    ├── test_policy_classifier.py
    └── test_rules.py
```

## Test configuration

`pyproject.toml` configures pytest with `pythonpath = ["src"]`, so tests can import the package from the `src/` layout without extra environment setup.
