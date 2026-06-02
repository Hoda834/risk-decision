# risk-decision

A reproducible, auditable, and explainable risk-based decision framework.

This repository contains **two complementary components** that share the same
risk-governance philosophy but are deliberately kept separate:

| Component | Location | What it is |
|-----------|----------|------------|
| **Decision Engine** | `src/risk_decision/` | A library (plus CLI and Streamlit demo) that turns risk indicators into an auditable, reproducible decision via a `scorer → aggregator → classifier → rules → explainability → audit` pipeline. |
| **Risk Decision Wizard** | `wizard/` | An interactive Streamlit application that guides a user through a question-bank wizard, validates input with pydantic, versions cases, and locks evaluation snapshots. |

They do not import from each other. Pick whichever fits your use case, or run
both.

## Repository layout

```text
risk-decision/
├── README.md
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── docs/
│   ├── policy_engine_v1.md
│   └── usage_guide.md
│
├── src/                         # Component 1: the Decision Engine (installable package)
│   └── risk_decision/
│       ├── __init__.py
│       ├── cli/
│       │   └── main.py          # `python -m risk_decision.cli.main <input.json>`
│       ├── core/
│       │   ├── decision_engine.py
│       │   ├── decision_types.py
│       │   └── fingerprints.py
│       ├── domain/
│       │   ├── activities.py
│       │   ├── categories.py
│       │   ├── domains.py
│       │   ├── indicators.py
│       │   └── schemas.py
│       ├── engine/
│       │   ├── scorer.py
│       │   ├── aggregator.py
│       │   ├── classifier.py    # BasicClassifier + PolicyAwareClassifier
│       │   ├── rules.py
│       │   ├── explainability.py
│       │   └── audit_trail.py
│       ├── io/
│       │   ├── loaders.py
│       │   └── exporters.py
│       ├── modules/             # placeholder for future domain modules
│       └── ui/
│           └── streamlit_app.py
│
├── tests/                       # tests for the Decision Engine
│   ├── test_decision_engine.py
│   ├── test_rules.py
│   └── test_audit_fingerprints.py
│
└── wizard/                      # Component 2: the interactive Risk Decision Wizard
    ├── run.sh
    ├── streamlit_app.py
    ├── config/
    │   ├── question_bank.json
    │   └── policy_config.json
    └── core/
        ├── wizard.py
        ├── engine.py
        ├── models.py
        ├── policy.py
        ├── questions.py
        ├── storage.py
        └── utils.py
```

## Installation

```bash
python -m pip install -e ".[test]"   # engine + test deps
# or, for a plain runtime install:
python -m pip install -r requirements.txt
```

Requires Python 3.10+.

## Component 1 — Decision Engine (`src/risk_decision/`)

Run the CLI against a JSON input describing `context` and `payload`:

```bash
PYTHONPATH=src python -m risk_decision.cli.main input.json
```

Or launch the engine's Streamlit demo:

```bash
PYTHONPATH=src streamlit run src/risk_decision/ui/streamlit_app.py
```

The pipeline is fully reproducible: identical inputs and config produce
identical input/config fingerprints in the audit trail.

## Component 2 — Risk Decision Wizard (`wizard/`)

```bash
./wizard/run.sh
# or:
cd wizard && streamlit run streamlit_app.py
```

The wizard writes case data (`cases/`, `drafts/`, `snapshots/`, `decisions/`)
into its working directory; these are git-ignored.

## Testing

`pyproject.toml` configures pytest with `pythonpath = ["src"]` and
`testpaths = ["tests"]`, so the engine tests run without extra setup:

```bash
pytest -q
```

CI (`.github/workflows/ci.yml`) runs the engine test suite on Python
3.10–3.12 and compile-checks the Wizard app on every push and pull request.

## Documentation

- [`docs/policy_engine_v1.md`](docs/policy_engine_v1.md) — policy engine design.
- [`docs/usage_guide.md`](docs/usage_guide.md) — usage guide.
