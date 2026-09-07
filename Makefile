.PHONY: help install dev test test-int test-all lint format typecheck pre-commit docs docs-serve clean fetch ingest eval report demo cases checkup checkup-fast all

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package in production mode
	$(PIP) install .

dev:  ## Install package with dev extras
	$(PIP) install -e ".[dev]"
	$(PYTHON) -m pre_commit install

test:  ## Run unit tests (no network)
	$(PYTHON) -m pytest tests/unit -v

test-int:  ## Run integration tests (offline, mocked)
	$(PYTHON) -m pytest tests/integration -v -m "not perf"

test-perf:  ## Run performance benchmarks (opt-in, slow)
	RUN_PERF=1 $(PYTHON) -m pytest tests/perf -v

test-all:  ## Run all tests
	$(PYTHON) -m pytest tests -v -m "not perf"

lint:  ## Run ruff linter
	$(PYTHON) -m ruff check src tests

format:  ## Format code with ruff
	$(PYTHON) -m ruff format src tests
	$(PYTHON) -m ruff check src tests --fix

typecheck:  ## Run mypy type checker
	$(PYTHON) -m mypy src/docendo

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
	docendo fetch

ingest:  ## Extract, chunk, embed, store in SQLite
	docendo ingest

eval:  ## Run the evaluation suite
	docendo eval

report:  ## Generate a Markdown report from results.jsonl
	docendo report

demo:  ## Launch the Streamlit A/B demo
	docendo demo

cases:  ## Show eval-dataset summary stats
	docendo cases

checkup:  ## Run local diagnostics (SQLite, vector ext, embedding/tokenizer)
	docendo checkup

checkup-fast:  ## Offline diagnostics (skip embedding + tokenizer probes)
	docendo checkup --no-embedding --no-tokenizer

all: dev lint typecheck test  ## Full local check (unit + integration)
