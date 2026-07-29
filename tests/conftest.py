"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bfsi_rbi.config import Settings, get_settings

_PLACEHOLDER_PATTERNS = {"test.es.example.com", "example.com", "localhost", "placeholder"}


def _is_placeholder_url(url: str) -> bool:
    url_lower = url.lower()
    return any(p in url_lower for p in _PLACEHOLDER_PATTERNS)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests don't leak env vars to one another."""
    test_env = {
        "MINIMAX_API_KEY": "test-key-not-real",
        "MINIMAX_BASE_URL": "https://api.minimax.io/v1",
        "MINIMAX_MODEL": "MiniMax-M3",
        "ELASTIC_URL": "https://test.es.example.com",
        "ELASTIC_API_KEY": "test-es-key-not-real",
        "ELASTIC_MCP_URL": "https://test.es.example.com/api/agent_builder/mcp",
        "BFSI_LOG_LEVEL": "WARNING",
        "BFSI_HTTP_TIMEOUT": "5",
    }
    for k, v in test_env.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def settings() -> Settings:
    """Fresh Settings instance (cache is bypassed)."""
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Empty raw/ dir under tmp_path."""
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    return raw


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip ``integration`` tests when running with placeholder creds."""
    # Read directly from .env to catch the file-based credentials
    elastic_url = os.getenv("ELASTIC_URL", "")
    if not elastic_url:
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("ELASTIC_URL="):
                    elastic_url = line.split("=", 1)[1].strip()
                    break
    if _is_placeholder_url(elastic_url):
        skip_integration = pytest.mark.skip(
            reason="Integration tests skipped: placeholder ELASTIC_URL"
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
