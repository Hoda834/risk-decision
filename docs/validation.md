# Validation record

Checked on 22 September 2026 with Python 3.12.

66 automated tests passed, comprising 59 retained tests and seven additional
lifecycle, closure, grounding, lock-bypass and provider-contract tests.
The wheel built successfully. An installation in a separate target directory,
run outside the source checkout, loaded packaged policy and questions.
Streamlit AppTest created a case and rendered Assessment, Describe issue,
Actions and review, and Register without exceptions.

The Ollama adapter was tested with a controlled subprocess response, not a live
model. There is no empirical extraction-accuracy result. No real organisational
case, multi-user deployment or scheduled notification was tested.

Code, tests and documentation were prepared with OpenAI Codex assistance.
The owner still needs to review the changes before public release. No human
review, independent adoption or JOSS eligibility is implied by these checks.
