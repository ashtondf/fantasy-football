PY := .venv/bin

.PHONY: install pull run test lint

install:
	$(PY)/pip install -e ".[dev]"

pull:
	$(PY)/sleeper-pull

run:
	$(PY)/streamlit run src/fantasy_league/ui/app.py

test:
	$(PY)/pytest

lint:
	$(PY)/ruff check src tests
	$(PY)/ruff format --check src tests