"""Integration tests for the eval pipeline.

These exercise the report generator and dataset loops end-to-end but
mock the LLM/agent calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from docendo.eval.driver import Outcome
from docendo.eval.judge import Verdict as Verdict
from docendo.eval.summarize import dump, render


@pytest.fixture
def _sample_results() -> list[Outcome]:
    return [
        Outcome(
            case_name="kyc",
            question="What is the KYC threshold?",
            gold_answer="INR 50,000 for cash transactions.",
            metadata={"topic": "factual"},
            grounded_answer="INR 50,000 for cash transactions.",
            grounded_citations=[{"circular_id": "RBI/2023-24/1"}],
            grounded_hallucination=Verdict(
                claims=[],
                total_claims=2,
                supported=2,
                contradicted=0,
                extra=0,
            ),
            ungrounded_answer="INR 50,000.",
            ungrounded_hallucination=Verdict(
                claims=[],
                total_claims=2,
                supported=1,
                contradicted=0,
                extra=1,
            ),
        ),
        Outcome(
            case_name="npa",
            question="How is NPA classified?",
            gold_answer="90+ days overdue.",
            metadata={"topic": "procedural"},
            grounded_answer="90+ days overdue.",
            grounded_citations=[{"circular_id": "RBI/2023-24/2"}],
            grounded_hallucination=Verdict(
                claims=[],
                total_claims=1,
                supported=1,
                contradicted=0,
                extra=0,
            ),
            ungrounded_answer="60+ days overdue.",
            ungrounded_hallucination=Verdict(
                claims=[],
                total_claims=1,
                supported=0,
                contradicted=1,
                extra=0,
            ),
        ),
    ]


class TestReportGeneration:
    def test_report_contains_tables(self, _sample_results: list[Outcome], tmp_path: Path) -> None:
        out = tmp_path / "report.md"
        render(_sample_results, out)
        assert out.exists()
        text = out.read_text()
        assert "docendo Evaluation Report" in text
        assert "Aggregate metrics" in text
        assert "By topic" in text
        assert "Per-case" in text
        assert "kyc" in text and "npa" in text
        assert "%" in text

    def test_aggregate_metrics(self, _sample_results: list[Outcome]) -> None:
        from docendo.eval.summarize import aggregate

        rep = aggregate(_sample_results)
        assert rep.grounded_hallucination_rate == pytest.approx(0.0)
        assert rep.ungrounded_hallucination_rate == pytest.approx(0.75)
        assert rep.grounded_citation_accuracy == 1.0

    def test_write_jsonl(self, _sample_results: list[Outcome], tmp_path: Path) -> None:
        out = tmp_path / "results.jsonl"
        dump(_sample_results, out)
        lines = out.read_text().splitlines()
        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert "case_name" in data
            assert "grounded_hallucination" in data

    def test_jsonl_round_trip_preserves_claims(self, _sample_results: list[Outcome], tmp_path: Path) -> None:
        """claims field survives the JSONL round-trip."""
        out = tmp_path / "results.jsonl"
        dump(_sample_results, out)
        for line in out.read_text().splitlines():
            data = json.loads(line)
            assert "claims" in data["grounded_hallucination"]
            assert "claims" in data["ungrounded_hallucination"]
