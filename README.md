# risk-decision
A reproducible, auditable, and explainable risk-based decision framework

```
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
├── src/
│   └── risk_decision/
│       ├── __init__.py
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── activities.py
│       │   ├── domains.py
│       │   ├── categories.py
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
│       ├── io/
│       │   ├── __init__.py
│       │   ├── loaders.py
│       │   └── exporters.py
│       └── cli/
│           ├── __init__.py
│           └── main.py
└── tests/
```
