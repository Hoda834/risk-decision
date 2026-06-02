#!/usr/bin/env bash
# Launch the Risk Decision Wizard.
# Run from anywhere: ./wizard/run.sh
set -euo pipefail
cd "$(dirname "$0")"
streamlit run streamlit_app.py
