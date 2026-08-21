#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
exec streamlit run streamlit_app.py "$@"
