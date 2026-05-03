.PHONY: help install test validate api web up up-full clean release version sync-version

PYTHON ?= python
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_DIR := apps/web
VERSION_FILE := VERSION

help:
	@echo "UAR quick commands"
	@echo "  make install       Install Python development dependencies"
	@echo "  make test          Run foundation Python tests"
	@echo "  make validate      Install and run foundation validation"
	@echo "  make api           Start the FastAPI runtime server"
	@echo "  make web           Start the staged web UI"
	@echo "  make up            One-command runtime launch: install + API"
	@echo "  make up-full       One-command full launch: install + API + staged UI"
	@echo "  make version       Show current version"
	@echo "  make sync-version  Sync VERSION into pyproject.toml"
	@echo "  make release       Validate, sync version, tag git repo, and push tag"
	@echo "  make clean         Remove local runtime artifacts"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e '.[dev]'

test:
	pytest tests/test_*.py

validate: install test

api:
	uvicorn uar.api.server:app --reload --host $(API_HOST) --port $(API_PORT)

web-build:
	cd $(WEB_DIR) && npm install && npm run build

up: install api

up-full: install
	@echo "Starting staged web UI and API runtime"
	@(cd $(WEB_DIR) && npm install && npm run dev) & \
	uvicorn uar.api.server:app --reload --host $(API_HOST) --port $(API_PORT)

version:
	@cat $(VERSION_FILE)

sync-version:
	@$(PYTHON) -c "from pathlib import Path; import re; version=Path('VERSION').read_text().strip(); path=Path('pyproject.toml'); text=path.read_text(); text=re.sub(r'^version = \".*\"', f'version = \"{version}\"', text, flags=re.MULTILINE); path.write_text(text); print(f'Synced pyproject.toml to version {version}')"

release: validate sync-version
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
