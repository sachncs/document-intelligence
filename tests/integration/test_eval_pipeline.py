"""Integration tests for the eval pipeline.

These exercise the report generator and dataset loops end-to-end but
mock the LLM/agent calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from docendo.eval.hallucination import HallucinationResult
from docendo.eval.report import generate_report, write_jsonl
from docendo.eval.runner import CaseResult


@pytest.fixture
def sample_results() -> list[CaseResult]:
    return [
        CaseResult(
            case_name="kyc",
            question="What is the KYC threshold?",
            gold_answer="INR 50,000 for cash transactions.",
            metadata={"topic": "factual"},
            grounded_answer="INR 50,000 for cash transactions.",
            grounded_citations=[{"circular_id": "RBI/2023-24/1"}],
            grounded_hallucination=HallucinationResult(
                claims=[],
                total_claims=2,
                supported=2,
                contradicted=0,
                extra=0,
            ),
            ungrounded_answer="INR 50,000.",
            ungrounded_hallucination=HallucinationResult(
                claims=[],
                total_claims=2,
                supported=1,
                contradicted=0,
                extra=1,
            ),
        ),
        CaseResult(
            case_name="npa",
            question="How is NPA classified?",
            gold_answer="90+ days overdue.",
            metadata={"topic": "procedural"},
            grounded_answer="90+ days overdue.",
            grounded_citations=[{"circular_id": "RBI/2023-24/2"}],
            grounded_hallucination=HallucinationResult(
                claims=[],
                total_claims=1,
                supported=1,
                contradicted=0,
                extra=0,
            ),
            ungrounded_answer="60+ days overdue.",
            ungrounded_hallucination=HallucinationResult(
                claims=[],
                total_claims=1,
                supported=0,
                contradicted=1,
                extra=0,
            ),
        ),
    ]


class TestReportGeneration:
    def test_report_contains_tables(self, sample_results: list[CaseResult], tmp_path: Path) -> None:
        out = tmp_path / "report.md"
        generate_report(sample_results, out)
        assert out.exists()
        text = out.read_text()
        assert "BFSI-RBI Evaluation Report" in text
        assert "Aggregate metrics" in text
        assert "By topic" in text
        assert "Per-case" in text
        assert "kyc" in text and "npa" in text
        # Relative reduction
        assert "relative_reduction" not in text  # We use friendly phrasing
        assert "%" in text

    def test_aggregate_metrics(self, sample_results: list[CaseResult]) -> None:
        from docendo.eval.report import _aggregate

        rep = _aggregate(sample_results)
        # Grounded: 0/2 + 0/1 averaged = 0
        assert rep.grounded_hallucination_rate == pytest.approx(0.0)
        # Ungrounded: 1/2 + 1/1 averaged = 0.75
        assert rep.ungrounded_hallucination_rate == pytest.approx(0.75)
        # Both cited
        assert rep.grounded_citation_accuracy == 1.0

    def test_write_jsonl(self, sample_results: list[CaseResult], tmp_path: Path) -> None:
        out = tmp_path / "results.jsonl"
        write_jsonl(sample_results, out)
        lines = out.read_text().splitlines()
        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert "case_name" in data
            assert "grounded_hallucination" in data
