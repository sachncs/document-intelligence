"""CLI end-to-end test for `docendo eval` with mocked LLM."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from docendo.config import reset_settings_cache


@pytest.fixture(autouse=True)
def _env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORE_PATH", str(tmp_path / "docendo.sqlite3"))
    monkeypatch.setenv("VECTOR_KEY", "test-key")
    monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
    monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
    monkeypatch.setenv("VECTOR_DIMS", "4")
    monkeypatch.setenv("CHAT_KEY", "test-key")
    monkeypatch.setenv("EVAL_CONCURRENCY", "1")
    reset_settings_cache()
    yield
    reset_settings_cache()


runner = CliRunner()


class TestEvalSmoke:
    def test_driver_run_writes_jsonl_per_outcome(
        self, tmp_path: Path
    ) -> None:
        """Bypass the CLI wrapper and exercise eval.driver.run directly so we
        don't depend on pydantic-ai internals."""
        from docendo.eval.cases import Case
        from docendo.eval.driver import run as driver_run

        cases = [
            Case(
                name=f"case_{i}",
                inputs=f"What is rule {i}?",
                expected_output=f"Rule {i} answer.",
                metadata={"topic": "kyc"},
            )
            for i in range(5)
        ]
        out = tmp_path / "results.jsonl"



        outcome = type("O", (), {"to_dict": lambda self: {
            "case_name": "x",
            "question": "q",
            "gold_answer": "a",
            "metadata": {},
            "grounded_answer": "a",
            "grounded_citations": [],
            "grounded_hallucination": {"total_claims": 0, "supported": 0, "contradicted": 0, "extra": 0, "hallucination_rate": 0, "grounding_score": 1.0, "claims": []},
            "ungrounded_answer": "a",
            "ungrounded_hallucination": {"total_claims": 0, "supported": 0, "contradicted": 0, "extra": 0, "hallucination_rate": 0, "grounding_score": 1.0, "claims": []},
        }})()

        def _fake_outcome_sync(*args, **kwargs):
            return outcome

        with (
            patch(
                "docendo.eval.driver.run_case",
                side_effect=_fake_outcome_sync,
            ),
        ):
            driver_run(cases, concurrency=1, output_path=out, settings=None)
        assert out.exists()
        lines = out.read_text().splitlines()
        assert len(lines) == 5
