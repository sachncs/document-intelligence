"""Tests for the ``docendo doctor`` CLI command."""

from __future__ import annotations

import io

import pytest

from docendo.cli.checkup import run_doctor
from docendo.config import reset_settings_cache


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BFSI_SQLITE_PATH", str(tmp_path / "rbi.sqlite3"))
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setenv("BFSI_EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("BFSI_EMBEDDING_API_BASE", "https://embed.example.com")
    monkeypatch.setenv("BFSI_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("BFSI_TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("BFSI_EMBEDDING_DIMS", "4")
    reset_settings_cache()
    yield
    reset_settings_cache()


class TestDoctor:
    def test_offline_exits_zero(self, tmp_path) -> None:
        # With --no-embedding and --no-tokenizer, all sync checks pass.
        stream = io.StringIO()
        rc = run_doctor(
            do_embedding=False,
            do_tokenizer=False,
            stream=stream,
        )
        out = stream.getvalue()
        assert rc == 0, out
        assert "All checks passed" in out
        assert "sqlite_opens" in out
        assert "vector_extension" in out

    def test_missing_minimax_key_fails(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "")
        reset_settings_cache()
        stream = io.StringIO()
        rc = run_doctor(do_embedding=False, do_tokenizer=False, stream=stream)
        out = stream.getvalue()
        assert rc == 1
        assert "FAIL" in out
        assert "MINIMAX_API_KEY" in out

    def test_tokenizer_mismatch_fails(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("BFSI_TOKENIZER_MODEL", "Qwen/Qwen2-7B")
        reset_settings_cache()
        stream = io.StringIO()
        rc = run_doctor(do_embedding=False, do_tokenizer=False, stream=stream)
        out = stream.getvalue()
        assert rc == 1
        assert "tokenizer_match" in out
        assert "FAIL" in out

    def test_offline_completes_under_3_seconds(self, tmp_path) -> None:
        import time

        start = time.perf_counter()
        run_doctor(do_embedding=False, do_tokenizer=False, stream=io.StringIO())
        elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"doctor took {elapsed:.1f}s (budget 3s)"
