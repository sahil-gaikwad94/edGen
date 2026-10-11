PY := .venv/bin/python
PIP := .venv/bin/pip
UVICORN := .venv/bin/uvicorn
NPM := npm

.PHONY: install api web test seed clean smoke

install:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install fastapi 'uvicorn[standard]' pydantic pyyaml pytest httpx
	$(PIP) install -e packages/graph -e packages/twin -e packages/lesson-ir -e packages/foundry -e packages/planner
	@echo "Python deps installed. For the web app: cd apps/web && npm install"

# API server (binds 0.0.0.0 so the Arena preview can reach it via the web proxy)
api:
	$(UVICORN) apps.api.app.main:app --host 0.0.0.0 --port 8000 --reload

web:
	cd apps/web && $(NPM) run dev

test:
	$(PY) -m pytest

seed:
	$(PY) -m apps.api.app.seed

smoke:
	$(PY) scripts/smoke.py

clean:
	rm -rf .venv .pytest_cache data/*.db apps/web/.next
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
