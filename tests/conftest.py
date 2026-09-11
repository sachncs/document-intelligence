"""Top-level pytest fixtures shared across the test tree."""

from __future__ import annotations

from pathlib import Path

import pytest
from docendo.config import Settings, get_settings, reset_settings_cache
from docendo.retrieval._internal import reset as reset_internal


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers so unknown-marker warnings disappear."""
    config.addinivalue_line(
        "markers", "perf: opt-in performance budget benchmarks (set RUN_PERF=1)"
    )
    config.addinivalue_line(
        "markers", "integration: requires live embedding / MiniMax / Network"
    )


@pytest.fixture(autouse=True)
def _teardown_after_test() -> None:
    """Finalize per-test state so async stores cannot leak between tests.

    Clears the cached Settings and the cached retrieval store so the
    next test rebuilds them against its own env-mutation cycle. This
    runs for every test in every directory but does not mutate the
    environment, so it is safe to include in perf benchmarks.
    """
    yield
    reset_settings_cache()
    reset_internal()


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Shared env contract for tests that need a populated env namespace.

    Individual test directories (:mod:`tests.unit.conftest`,
    :mod:`tests.integration.conftest`) wrap this fixture with an
    autouse override so the env contract is always applied.
    """
    monkeypatch.setenv("STORE_PATH", str(tmp_path / "docendo.sqlite3"))
    monkeypatch.setenv("VECTOR_KEY", "test-key")
    monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
    monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("VECTOR_DIMS", "4")
    monkeypatch.setenv("CHAT_KEY", "test-key")
    reset_settings_cache()
    reset_internal()
    yield tmp_path
    reset_internal()


@pytest.fixture
def settings() -> Settings:
    """Fresh Settings instance (cache is bypassed)."""
    reset_settings_cache()
    return get_settings()


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Empty raw/ dir under tmp_path."""
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    return raw
