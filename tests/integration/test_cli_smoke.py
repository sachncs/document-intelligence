"""CLI smoke tests for docendo.

Run with `pytest tests/integration/test_cli_smoke.py -v` (no live network).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from docendo.cli.main import app
from typer.testing import CliRunner

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
