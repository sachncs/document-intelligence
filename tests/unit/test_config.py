"""Tests for Settings configuration."""

from __future__ import annotations

import pytest

from bfsi_rbi.config import Settings
from bfsi_rbi.exceptions import ConfigurationError


class TestSettings:
    def test_litellm_model_prefix(self, settings: Settings) -> None:
        assert settings.litellm_model == "minimax/MiniMax-M3"

    def test_require_llm_raises_on_empty(self, settings: Settings) -> None:
        settings.minimax_api_key = ""
        with pytest.raises(ConfigurationError):
            settings.require_llm()

    def test_require_elastic_raises_on_empty(self, settings: Settings) -> None:
        settings.elastic_url = ""
        settings.elastic_api_key = ""
        with pytest.raises(ConfigurationError):
            settings.require_elastic()

    def test_ensure_mcp_suffix_when_missing(self) -> None:
        s = Settings(
            elastic_url="https://example.es.cloud",
            elastic_mcp_url="",
        )
        assert s.elastic_mcp_url == "https://example.es.cloud/api/agent_builder/mcp"

    def test_ensure_mcp_suffix_preserves_explicit(self, settings: Settings) -> None:
        settings.elastic_mcp_url = "https://custom.example.com/mcp"
        assert settings.elastic_mcp_url == "https://custom.example.com/mcp"
