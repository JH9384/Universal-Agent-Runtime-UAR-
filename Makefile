.PHONY: help install test test-fast test-coverage test-backend test-frontend test-alignment test-regression lint lint-py lint-ts build-frontend validate validate-d4c d4c-result d4c-release-gate d4d-status api web dashboard up up-full up-all docker-up docker-up-full docker-smoke docker-down mcp-smoke mcp-server clean release version sync-version check-version

PYTHON ?= python3.12
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_DIR := apps/web
DASHBOARD_DIR := apps/operator-dashboard
VERSION_FILE := VERSION
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_STAMP := $(VENV)/.install-stamp
PYTEST := $(VENV_PYTHON) -m pytest
RUFF := $(VENV_PYTHON) -m ruff

help:
	@echo "UAR quick commands"
	@echo "  make install          Install Python development dependencies"
	@echo "  make test             Run all Python tests"
	@echo "  make test-fast        Run tests in parallel (pytest-xdist)"
	@echo "  make test-coverage    Run tests with coverage report"
	@echo "  make test-backend     Run backend tests (fast)"
	@echo "  make test-frontend    Run frontend tests (Vitest)"
	@echo "  make test-alignment   Run skill/feature/tips alignment tests"
	@echo "  make test-regression  Full regression: backend + frontend + build + lint"
	@echo "  make lint             Run all linters (Python + TS)"
	@echo "  make lint-py          Run Python linter (ruff)"
	@echo "  make lint-ts          Run TypeScript type check"
	@echo "  make build-frontend   Build production frontend bundle"
	@echo "  make validate         Install and run foundation validation"
	@echo "  make validate-d4c     Run focused D4C operator loop validation"
	@echo "  make d4c-result       Write D4C validation result stub"
	@echo "  make d4c-release-gate Run focused D4C validation and write result stub"
	@echo "  make d4d-status       Print D4D validation/burn-in sequence"
	@echo "  make validate-uor     Validate pinned UOR artifacts (SHACL + JSON Schema)"
	@echo "  make api              Start the FastAPI runtime server"
	@echo "  make web              Start the staged web UI"
	@echo "  make dashboard        Start the Mission Control dashboard"
	@echo "  make up               One-command runtime launch: install + API"
	@echo "  make up-full          One-command full launch: install + staged UI"
	@echo "  make up-all           One-command full launch: install + staged UI + dashboard"
	@echo "  make docker-up        Build and start Dockerized API runtime"
	@echo "  make docker-up-full   Build and start Dockerized API + staged UI"
	@echo "  make docker-smoke     Smoke-check Dockerized API runtime"
	@echo "  make docker-down      Stop Dockerized runtime"
	@echo "  make mcp-smoke        Validate read-only MCP tool registry"
	@echo "  make mcp-server       Start read-only MCP stdio server"
	@echo "  make version          Show current version"
	@echo "  make check-version    Verify VERSION matches pyproject.toml"
	@echo "  make sync-version     Sync VERSION into pyproject.toml"
	@echo "  make release          Validate, sync version, tag git repo, and push tag"
	@echo "  make clean            Remove local runtime artifacts"

$(VENV_STAMP): pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e '.[dev]'
	@touch $(VENV_STAMP)

install: $(VENV_STAMP)

test: $(VENV_STAMP)
	$(PYTEST) tests/ -q --tb=short

test-fast: $(VENV_STAMP)
	$(PYTEST) tests/ -q --tb=short -n auto

test-coverage: $(VENV_STAMP)
	$(PYTEST) tests/ -q --tb=short --cov=uar --cov-report=term-missing \
		--cov-report=html:htmlcov --junitxml=test-results.xml

test-backend: $(VENV_STAMP)
	$(PYTEST) tests/ -q --tb=short

test-frontend:
	cd $(WEB_DIR) && npm run test:run

test-alignment: $(VENV_STAMP)
	$(PYTEST) tests/skills/test_skill_alignment.py tests/docs/test_feature_alignment.py tests/docs/test_tips_alignment.py -v --tb=short

test-regression: test-backend test-frontend build-frontend lint
	@echo "========================================"
	@echo "  REGRESSION SUITE COMPLETE"
	@echo "========================================"

gate: test-backend lint
	@echo "========================================"
	@echo "  BURN-IN GATE"
	@echo "========================================"
	@echo "Running substrate validation..."
	$(PYTEST) tests/runtime/test_runtime_*.py -q --tb=short
	$(PYTEST) tests/runtime/test_replay_*.py -q --tb=short
	$(PYTEST) tests/runtime/test_timeline.py -q --tb=short
	@echo "========================================"
	@echo "  GATE PASSED"
	@echo "========================================"

lint: lint-py lint-ts

lint-py: $(VENV_STAMP)
	$(RUFF) check uar/ tests/ --select=E,W,F --ignore=E501

lint-ts:
	cd $(WEB_DIR) && npx tsc --noEmit

build-frontend:
	cd $(WEB_DIR) && npm run build

validate: check-version $(VENV_STAMP)
	$(PYTEST) tests/ -q --tb=short

validate-d4c:
	bash scripts/validate_d4c_operator_loop.sh

d4c-result:
	$(PYTHON) scripts/write_d4c_validation_result.py

d4c-release-gate: validate-d4c d4c-result
	@echo "========================================"
	@echo "  D4C RELEASE GATE COMPLETE"
	@echo "========================================"

d4d-status:
	@echo "D4D validation/burn-in sequence"
	@echo "1. make d4c-release-gate"
	@echo "2. record status with docs/operations/D4D_VALIDATION_STATUS_TEMPLATE.md"
	@echo "3. fix only validation failures"
	@echo "4. run make test-regression or decomposed backend/frontend/build checks"
	@echo "5. request explicit tag approval only after gates pass"

validate-uor: $(VENV_STAMP)
	$(VENV_PYTHON) scripts/validate_uor_alignment.py

api:
	uvicorn uar.api.server:app --reload --host $(API_HOST) --port $(API_PORT)

web-build:
	cd $(WEB_DIR) && npm install && npm run build

dashboard-build:
	cd $(DASHBOARD_DIR) && npm install && npm run build

up: install api

up-full: install
	@echo "Starting staged web UI and API runtime"
	@(cd $(WEB_DIR) && npm install && npm run dev) & \
	uvicorn uar.api.server:app --reload --host $(API_HOST) --port $(API_PORT)

up-all: install
	@echo "Starting API, staged web UI, and Mission Control"
	@(cd $(DASHBOARD_DIR) && npm install && npm run dev) & \
	(cd $(WEB_DIR) && npm install && npm run dev) & \
	uvicorn uar.api.server:app --reload --host $(API_HOST) --port $(API_PORT)

docker-up:
	docker compose up --build uar-api

docker-up-full:
	docker compose --profile web up --build

docker-smoke:
	bash scripts/docker_smoke.sh

docker-down:
	docker compose down

mcp-smoke: $(VENV_STAMP)
	$(VENV_PYTHON) scripts/mcp_smoke.py

mcp-server: $(VENV_STAMP)
	$(VENV_PYTHON) -m uar.mcp.server

web:
	cd $(WEB_DIR) && npm install && npm run dev

dashboard:
	cd $(DASHBOARD_DIR) && npm install && npm run dev

version:
	@cat $(VERSION_FILE)

check-version:
	@$(PYTHON) -c "from pathlib import Path; import re; version=Path('VERSION').read_text().strip(); text=Path('pyproject.toml').read_text(); match=re.search(r'^version = \"([^\"]+)\"', text, flags=re.MULTILINE); pyproject_version=match.group(1) if match else ''; assert pyproject_version == version, f'Version mismatch: VERSION={version} pyproject.toml={pyproject_version}'; print(f'Version OK: {version}')"

sync-version:
	@$(PYTHON) -c "from pathlib import Path; import re; version=Path('VERSION').read_text().strip(); path=Path('pyproject.toml'); text=path.read_text(); text=re.sub(r'^version = \".*\"', f'version = \"{version}\"', text, flags=re.MULTILINE); path.write_text(text); print(f'Synced pyproject.toml to version {version}')"

release: sync-version validate
	@VERSION=$$(cat $(VERSION_FILE)); \
	echo "Releasing version $$VERSION"; \
	git diff --exit-code VERSION pyproject.toml CHANGELOG.md RELEASE.md SYSTEM.md RELEASE_CHECKLIST.md; \
	git tag -a v$$VERSION -m "UAR release v$$VERSION"; \
	git push origin v$$VERSION

clean:
	rm -rf .pytest_cache
	rm -rf **/__pycache__
	rm -rf runs
	rm -f uar.sqlite3
	rm -rf $(WEB_DIR)/dist
	rm -rf $(WEB_DIR)/node_modules/.vite
	rm -rf $(WEB_DIR)/node_modules/.cache
	rm -rf $(DASHBOARD_DIR)/dist
	rm -rf $(DASHBOARD_DIR)/node_modules/.vite
	rm -rf $(DASHBOARD_DIR)/node_modules/.cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache

docker-security:
	bash scripts/docker_security_check.sh
