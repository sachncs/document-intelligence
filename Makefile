.PHONY: help install dev test lint format typecheck pre-commit docs clean fetch ingest setup-inference deploy-tools deploy-agent smoke-mcp eval report demo all

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package in production mode
	$(PIP) install .

dev:  ## Install package with dev extras
	$(PIP) install -e ".[dev]"
	$(PYTHON) -m pre_commit install

test:  ## Run unit tests
	$(PYTHON) -m pytest tests/unit -v

test-integration:  ## Run integration tests (requires live services)
	$(PYTHON) -m pytest tests/integration -v -m integration

test-all:  ## Run all tests
	$(PYTHON) -m pytest tests -v

lint:  ## Run ruff linter
	$(PYTHON) -m ruff check src tests

format:  ## Format code with ruff
	$(PYTHON) -m ruff format src tests
	$(PYTHON) -m ruff check src tests --fix

typecheck:  ## Run mypy type checker
	$(PYTHON) -m mypy src/bfsi_rbi

pre-commit:  ## Run all pre-commit hooks
	$(PYTHON) -m pre_commit run --all-files

docs:  ## Build docs site
	$(PYTHON) -m mkdocs build

docs-serve:  ## Serve docs locally
	$(PYTHON) -m mkdocs serve

clean:  ## Remove build artifacts
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

fetch:  ## Fetch RBI documents
	bfsi-rbi fetch

ingest:  ## Ingest documents into Elasticsearch
	bfsi-rbi ingest

setup-inference:  ## Setup ELSER inference endpoint
	bfsi-rbi setup-inference

deploy-tools:  ## Deploy Agent Builder tools to Kibana
	bfsi-rbi deploy-tools

deploy-agent:  ## Deploy Agent Builder agent to Kibana
	bfsi-rbi deploy-agent

smoke-mcp:  ## Smoke-test MCP connection
	bfsi-rbi smoke-mcp

eval:  ## Run evaluation
	bfsi-rbi eval

report:  ## Generate eval report
	bfsi-rbi report

demo:  ## Launch Streamlit demo
	bfsi-rbi demo

all: dev lint typecheck test  ## Full local check
