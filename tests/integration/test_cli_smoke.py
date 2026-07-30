"""CLI smoke tests for docendo.

Run with `pytest tests/integration/test_cli_smoke.py -v` (no live network).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from docendo.cli.main import app
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
    reset_settings_cache()
    yield
    reset_settings_cache()


runner = CliRunner()


class TestHelp:
    def test_help_lists_subcommands(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ("fetch", "ingest", "eval", "report", "demo", "cases", "checkup"):
            assert cmd in result.stdout, f"subcommand {cmd} missing from --help"


class TestCheckup:
    def test_checkup_offline_exits_zero(self) -> None:
        result = runner.invoke(
            app, ["checkup", "--no-embedding", "--no-tokenizer"]
        )
        assert result.exit_code == 0
        assert "All checks passed" in result.stdout


class TestCases:
    def test_cases_exit_zero(self, tmp_path: Path) -> None:
        cases_path = tmp_path / "cases.yaml"
        cases_path.write_text(
            yaml.safe_dump(
                [
                    {
                        "name": "kyc",
                        "inputs": "What is KYC?",
                        "expected_output": "Know Your Customer.",
                        "metadata": {"topic": "kyc"},
                    }
                ]
            )
        )
        result = runner.invoke(app, ["cases", "--dataset", str(cases_path)])
        assert result.exit_code == 0
        assert "Total cases: 1" in result.stdout


class TestReport:
    def test_report_exit_zero_on_minimal_jsonl(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "results.jsonl"
        jsonl.write_text(
            '{"case_name": "kyc", "question": "q", "gold_answer": "a", '
            '"metadata": {}, "grounded_answer": "a", "grounded_citations": [], '
            '"grounded_hallucination": {"total_claims": 0, "supported": 0, '
            '"contradicted": 0, "extra": 0, "hallucination_rate": 0, '
            '"grounding_score": 0, "claims": []}, '
            '"ungrounded_answer": "a", "ungrounded_hallucination": null}\n'
        )
        out = tmp_path / "report.md"
        result = runner.invoke(app, ["report", str(jsonl), "--out", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        text = out.read_text()
        assert "docendo Evaluation Report" in text
