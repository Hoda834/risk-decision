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

---

# Second pass: risk logic and governance

Policy v1.1 to v1.2. The code was correct after the first pass. The method was not.

## Categorisation now reads a matrix

v1.1 multiplied two normalised ordinal scales. That produced 25 cells of which
9 scored exactly 0.00, because `(1-1)/4 = 0` annihilates the other axis, and 13
returned ACCEPT. An unlikely major impact, cell (2,4), scored 0.19 and returned
ACCEPT with no escalation.

v1.2 does not aggregate. `scoring.category_matrix` holds an explicit category per
cell, and the ordinal product is kept only as an ordering value, labelled as such
in the UI. Load fails if the grid is not monotonic in either direction, if a row
is missing, or if a cell names an unknown category.

Cell (1,4) moved from low ACCEPT to medium REDUCE. Cell (2,4) likewise.

Two test assertions changed with it, both tied to the old formula:
`test_catastrophic_impact_cannot_be_classified_low` asserted the score was
exactly 0.0, now asserts it stays below the low band while the category is high,
which is the behaviour the test name describes.
`test_finish_locks_and_populates_the_snapshot` moved from 0.5625 to 0.625.

## Governance is enforced rather than described

- The authority matrix is wired. It caps acceptance by category, not by score,
  and no role may accept a critical risk. Load fails if a role is granted more
  than the hard block allows.
- An outcome the assessor marked "Not acceptable" blocks acceptance at any level.
  The field was collected and ignored before.
- Confidence of 2 or below forces escalation without touching the category.
  Also collected and ignored before.
- Every escalation records its reason on the snapshot.
- An escalated case needs a second person, and the approver cannot be the person
  recording the decision.
- A review date is required and defaults from the time to impact, which was the
  fourth field collected and never used.

## Integrity is checked, not just written

- `inputs_hash` is verified on load. `core/integrity.py` reports a case whose
  inputs no longer match the hash recorded at evaluation.
- A locked version refuses a write that would change its assessed inputs.
  Decision changes are still allowed.
- The audit log is hash-chained. An edited or removed entry breaks the chain and
  `verify_audit_log` names the entry.

## Tests

59 pass, up from 34. New: `tests/test_matrix.py` and `tests/test_governance.py`.

## Still open, and deliberately not changed here

- No frequency anchors on the likelihood labels and no per-domain severity
  descriptors. This is the largest remaining threat to assessment reliability.
- No risk controls, residual risk or benefit-risk analysis, so a case can be
  decided but not closed.
- The taxonomy in `src/risk_decision/domain/` is still not wired into the wizard,
  so identification has no prompt list.
- `anchor.direction` records upside, and the decision vocabulary is downside only.
- The batch engine still averages indicator scores per domain, which hides one
  severe indicator among many mild ones.
