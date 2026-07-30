"""Tests for the ``docendo checkup`` CLI command."""

from __future__ import annotations

import io

import pytest

from docendo.cli.checkup import run
from docendo.config import reset_settings_cache


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORE_PATH", str(tmp_path / "docendo.sqlite3"))
    monkeypatch.setenv("CHAT_KEY", "test-key")
    monkeypatch.setenv("VECTOR_KEY", "test-key")
    monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
    monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("VECTOR_DIMS", "4")
    reset_settings_cache()
    yield
    reset_settings_cache()


class TestCheckup:
    def test_offline_exits_zero(self, tmp_path) -> None:
        stream = io.StringIO()
        rc = run(
            do_embedding=False,
            do_tokenizer=False,
            stream=stream,
        )
        out = stream.getvalue()
        assert rc == 0, out
        assert "All checks passed" in out
        assert "sqlite_opens" in out
        assert "vector_extension" in out

    def test_missing_chat_key_fails(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("CHAT_KEY", "")
        reset_settings_cache()
        stream = io.StringIO()
        rc = run(do_embedding=False, do_tokenizer=False, stream=stream)
        out = stream.getvalue()
        assert rc == 1
        assert "FAIL" in out
        assert "CHAT_KEY" in out

    def test_tokenizer_mismatch_fails(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen2-7B")
        monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
        reset_settings_cache()
        stream = io.StringIO()
        rc = run(do_embedding=False, do_tokenizer=False, stream=stream)
        out = stream.getvalue()
        assert rc == 1
        assert "tokenizer_match" in out
        assert "FAIL" in out

    def test_offline_completes_under_3_seconds(self, tmp_path) -> None:
        import time

        start = time.perf_counter()
        run(do_embedding=False, do_tokenizer=False, stream=io.StringIO())
        elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"checkup took {elapsed:.1f}s (budget 3s)"
