"""Tests for the agent factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from docendo.agent import GRCIT_SYSTEM_PROMPT, _cached_litellm_model, _tool_functions, make_agent
from docendo.config import reset_settings_cache


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key-not-real")
    monkeypatch.setenv("BFSI_EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("BFSI_EMBEDDING_API_BASE", "https://embed.example.com")
    monkeypatch.setenv("BFSI_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("BFSI_TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("BFSI_EMBEDDING_DIMS", "4")
    reset_settings_cache()
    yield
    reset_settings_cache()


class TestAgentFactory:
    def test_grounded_has_four_tools(self) -> None:
        with patch("docendo.agent.Agent") as mock_agent:
            mock_agent.return_value = MagicMock()
            make_agent(grounded=True)
        tools_arg = mock_agent.call_args.kwargs.get("tools")
        assert tools_arg is not None
        assert len(tools_arg) == 4
        names = {t.__name__ for t in tools_arg}
        assert names == {
            "hybrid_search",
            "get_circular",
            "list_recent",
            "compare_circulars",
        }

    def test_ungrounded_has_no_tools(self) -> None:
        with patch("docendo.agent.Agent") as mock_agent:
            mock_agent.return_value = MagicMock()
            make_agent(grounded=False)
        tools_arg = mock_agent.call_args.kwargs.get("tools")
        assert tools_arg == []

    def test_grounded_uses_rbi_answer_output_type(self) -> None:
        with patch("docendo.agent.Agent") as mock_agent:
            mock_agent.return_value = MagicMock()
            make_agent(grounded=True)
        from docendo.models import RBIAnswer

        assert mock_agent.call_args.kwargs.get("output_type") is RBIAnswer

    def test_system_prompt_mentions_tools(self) -> None:
        assert "hybrid_search" in GRCIT_SYSTEM_PROMPT
        assert "get_circular" in GRCIT_SYSTEM_PROMPT
        assert "list_recent" in GRCIT_SYSTEM_PROMPT
        assert "compare_circulars" in GRCIT_SYSTEM_PROMPT


class TestRetrieverCaching:
    def test_retriever_is_cached(self, tmp_path, monkeypatch) -> None:
        """Two calls to get_retriever with the same path return the same store."""
        db = tmp_path / "rbi.sqlite3"
        monkeypatch.setenv("BFSI_SQLITE_PATH", str(db))
        monkeypatch.setenv("BFSI_EMBEDDING_DIMS", "4")
        reset_settings_cache()
        from docendo.retrieval.factory import get_retriever, reset_retriever_cache

        reset_retriever_cache()
        a = get_retriever()
        b = get_retriever()
        assert a is b
        reset_retriever_cache()


class TestLiteLLMSingleton:
    def test_litellm_model_is_singleton(self) -> None:
        _cached_litellm_model.cache_clear()
        a = _cached_litellm_model()
        b = _cached_litellm_model()
        assert a is b


class TestToolFunctions:
    def test_tool_function_names(self) -> None:
        names = {t.__name__ for t in _tool_functions()}
        assert names == {
            "hybrid_search",
            "get_circular",
            "list_recent",
            "compare_circulars",
        }
