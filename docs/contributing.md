# Contributing

## Development setup

```bash
git clone https://github.com/sachin/bfsi-rbi
cd bfsi-rbi
pip install -e ".[dev]"
pre-commit install
```

## Workflow

1. Fork & create a feature branch
2. Make changes
3. Run `pytest tests/unit` and `ruff check src tests`
4. Commit & push
5. Open a Pull Request

## Code style

- Type hints throughout (strict mypy)
- Line length 100 (ruff)
- Google-style docstrings
- One `pytest` test per behavior

## Adding eval cases

Append to `eval/dataset.yaml`. Each case must have a unique `name`, a
`topic` (one of `factual | procedural | cross_circular | date_bounded |
trap`), and a gold answer sourced from an official RBI document.
