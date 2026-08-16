#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/streamlit run src/fantasy_league/ui/app.py "$@"