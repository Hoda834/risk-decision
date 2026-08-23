# Fixes applied

The wizard and two test modules were written against a version of `core/` that
was never committed. That single gap produced most of what follows.

## Blockers

- `streamlit_app.py` imported four functions that did not exist (`is_locked`,
  `outstanding_steps`, `step_errors`, `validate_answer`) and called five others
  with the wrong signature. The app now matches `core/`, and
  `tests/test_app_flow.py` imports it so the drift cannot come back silently.
- `core/engine.py` built `EvaluationSnapshot` from five fields the model did not
  have. Rewritten. `EvaluationSnapshot` now carries the full documented shape.
- `core/wizard.py` rewritten: policy-driven scoring, `outstanding_steps`,
  `step_errors`, `validate_answer`, `is_locked`, and a blank owner no longer
  raises on lock.
- `run.sh` is now executable. Apply the mode change in git with
  `git update-index --add --chmod=+x run.sh` if it does not carry over.
- `pyproject.toml` gains a console script, so `python -m risk_decision.cli.main`
  works after `pip install -e ".[dev]"`. Added `input.example.json`.

## Scoring

- One scoring path, not two. The wizard now calls `core/engine.py`, which reads
  `config/policy_config.json`. The hardcoded `raw/5` normalisation and the
  hardcoded 0.2/0.5 thresholds are gone.
- Policy scales moved from 1 to 3 back to 1 to 5, matching the models, the
  sliders, the tests and `docs/policy_engine.md`. Under the old config, levels
  3, 4 and 5 all normalised to 1.0.
- Decision mapping is now by category and uses `DecisionType`, so the lowercase
  policy output no longer breaks the override selectbox.
- Overrides implemented as config: catastrophic impact floors the category at
  high, irreversible floors at medium, privacy keywords set escalation. They can
  raise a category, never lower it.

## Audit trail

- `inputs_hash` is SHA-256 over assessed inputs only. Derived values are excluded
  by construction in `hashable_inputs`, not by hoping the caller left them out.
  It was SHA-1 over a dict that included the normalised values.
- All models reject unknown fields. The recorded override reason and
  `follows_recommendation` were silently dropped before; both are now stored.
- `anchor.direction` exists on the model, so the answer is no longer discarded.
- Widget keys are scoped to case and version. Switching case in the sidebar
  showed, and could save, the previous case's answers.
- Case ids are validated before they become directory names.

## Question bank

- Options resolve against the model enums and the policy scales at load time.
  Unknown enum, step, path or duplicate id raises on load.
- Every option set now matches the model. None of them did.
- Added the seven questions for required fields that had none: consequences,
  scope, data used, references, time to impact, and both confidence values.

## Repo

- Deleted seven empty files named `download`, the duplicate `core/decision_*.py`
  and `core/fingerprints.py`, and the duplicate `src/*.py` modules.
- Added `.gitignore`. Case data writes to `data/`, not the repo root.
- Docs moved to `docs/`. README now matches the code.
- Added `.github/workflows/tests.yml`.
- Batch engine warns when domain scores and classifier thresholds are on
  different scales, instead of returning APPROVE for everything.

## Tests

34 pass. Was 8 passing, 19 uncollectable.
