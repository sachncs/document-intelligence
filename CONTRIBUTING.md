# Contributing

Contributions are welcome. Please open an issue first to discuss substantial changes.

## Development setup

```bash
git clone https://github.com/sachin/bfsi-rbi
cd bfsi-rbi
pip install -e ".[dev]"
pre-commit install
```

## Workflow

1. Fork & create a feature branch (`git checkout -b feat/my-change`)
2. Make changes
3. Run tests: `pytest tests/unit`
4. Run lint: `ruff check src tests && ruff format src tests`
5. Run typecheck: `mypy src/bfsi_rbi`
6. Commit & push
7. Open a Pull Request

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`.

## Code style

- Type hints throughout
- No `Any` except at integration boundaries
- Public functions get docstrings
- Tests for new features
