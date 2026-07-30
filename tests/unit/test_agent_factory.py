"""Tests for the agent factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from docendo.agent import SYSTEM_PROMPT, agent, model, reset, tools
from docendo.config import reset_settings_cache


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAT_KEY", "test-key-not-real")
    monkeypatch.setenv("VECTOR_KEY", "test-key")
    monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
    monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("VECTOR_DIMS", "4")
    reset_settings_cache()
    yield
    reset_settings_cache()


class TestAgentFactory:
    def test_grounded_has_four_tools(self) -> None:
        with patch("docendo.agent.PydanticAgent") as mock_agent:
            mock_agent.return_value = MagicMock()
            agent(grounded=True)
        tools_arg = mock_agent.call_args.kwargs.get("tools")
        assert tools_arg is not None
        assert len(tools_arg) == 4
        names = {t.__name__ for t in tools_arg}
        assert names == {"search", "fetch", "recent", "compare"}

    def test_ungrounded_has_no_tools(self) -> None:
        with patch("docendo.agent.PydanticAgent") as mock_agent:
            mock_agent.return_value = MagicMock()
            agent(grounded=False)
        tools_arg = mock_agent.call_args.kwargs.get("tools")
        assert tools_arg == []

    def test_grounded_uses_answer_output_type(self) -> None:
        from docendo.models import Answer

        with patch("docendo.agent.PydanticAgent") as mock_agent:
            mock_agent.return_value = MagicMock()
            agent(grounded=True)
        assert mock_agent.call_args.kwargs.get("output_type") is Answer

    def test_system_prompt_mentions_tools(self) -> None:
        assert "search" in SYSTEM_PROMPT
        assert "fetch" in SYSTEM_PROMPT
        assert "recent" in SYSTEM_PROMPT
        assert "compare" in SYSTEM_PROMPT


class TestRetrieverCaching:
    def test_retriever_is_cached(self, tmp_path, monkeypatch) -> None:
        db = tmp_path / "docendo.sqlite3"
        monkeypatch.setenv("STORE_PATH", str(db))
        monkeypatch.setenv("VECTOR_DIMS", "4")
        reset_settings_cache()
        from docendo.retrieval._internal import get, reset as reset_internal

        reset_internal()
        a = get()
        b = get()
        assert a is b
        reset_internal()


class TestLiteLLMSingleton:
    def test_model_is_singleton(self) -> None:
        reset()
        a = model()
        b = model()
        assert a is b
        reset()

    def test_settings_change_invalidates_model(self) -> None:
        """When the chat id changes, model() rebuilds."""
        from docendo.config import reset_settings_cache

        reset()
        reset_settings_cache()
        a = model()
        # Different chat_url -> different cached instance.
        b = model("https://other.example.com", "k", "Other")
        assert a is not b


class TestToolFunctions:
    def test_tool_function_names(self) -> None:
        names = {t.__name__ for t in tools()}
        assert names == {"search", "fetch", "recent", "compare"}
