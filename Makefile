.PHONY: help install test validate api web up up-full clean release version

PYTHON ?= python
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_DIR := apps/web
VERSION_FILE := VERSION

help:
	@echo "UAR quick commands"
	@echo "  make install    Install Python development dependencies"
	@echo "  make test       Run foundation Python tests"
	@echo "  make validate   Install and run foundation validation"
	@echo "  make api        Start the FastAPI runtime server"
	@echo "  make web        Start the staged web UI"
	@echo "  make up         One-command runtime launch: install + API"
	@echo "  make up-full    One-command full launch: install + API + staged UI"
	@echo "  make release    Tag git repo with VERSION and push"
	@echo "  make version    Show current version"
	@echo "  make clean      Remove local runtime artifacts"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e '.[dev]'

test:
	pytest tests/test_*.py

validate: install test

api:
	uvicorn uar.api.server:app --reload --host $(API_HOST) --port $(API_PORT)

web:
	cd $(WEB_DIR) && npm install && npm run dev

up: install api

up-full: install
	@echo "Starting staged web UI and API runtime"
	@(cd $(WEB_DIR) && npm install && npm run dev) & \
	uvicorn uar.api.server:app --reload --host $(API_HOST) --port $(API_PORT)

version:
	@cat $(VERSION_FILE)

release:
	@VERSION=$$(cat $(VERSION_FILE)); \
	echo "Releasing version $$VERSION"; \
	git tag -a v$$VERSION -m "UAR release v$$VERSION"; \
	git push origin v$$VERSION

clean:
	rm -rf .pytest_cache
	rm -rf **/__pycache__
	rm -rf runs
	rm -f uar.sqlite3
