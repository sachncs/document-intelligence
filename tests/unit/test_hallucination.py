"""Tests for the atomic-claim hallucination evaluator.

Mocks the LLM to avoid network calls and verify the algorithm.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

import pytest

from docendo.eval.judge import (
    evaluate_answer,
)


def _litellm_response(content: str) -> Mock:
    """Build a mock LiteLLM response object."""
    resp = Mock()
    resp.choices = [Mock()]
    resp.choices[0].message.content = content
    return resp


class TestEvaluateAnswer:
    def test_perfect_answer(self, settings: Any) -> None:
        with (
            patch("docendo.eval.judge.completion") as mock,
        ):
            mock.side_effect = [
                _litellm_response('["X is 1.", "Y is 2."]'),
                _litellm_response('{"verdict": "supported", "reason": "ok"}'),
                _litellm_response('{"verdict": "supported", "reason": "ok"}'),
            ]
            result = evaluate_answer(
                "X is 1. Y is 2.",
                "X is 1. Y is 2.",
                settings=settings,
            )
        assert result.total_claims == 2
        assert result.supported == 2
        assert result.hallucination_rate == 0.0

    def test_contradicted_and_extra(self, settings: Any) -> None:
        with patch("docendo.eval.judge.completion") as mock:
            mock.side_effect = [
                _litellm_response('["X is 1.", "Y is 2.", "Z is 3."]'),
                _litellm_response('{"verdict": "supported", "reason": "ok"}'),
                _litellm_response('{"verdict": "contradicted", "reason": "wrong"}'),
                _litellm_response('{"verdict": "extra", "reason": "not in gold"}'),
            ]
            result = evaluate_answer(
                "X is 1. Y is 99. Z is 3.",
                "X is 1. Y is 2.",
                settings=settings,
            )
        assert result.total_claims == 3
        assert result.supported == 1
        assert result.contradicted == 1
        assert result.extra == 1
        assert result.hallucination_rate == pytest.approx(2 / 3)

    def test_empty_claims(self, settings: Any) -> None:
        with patch("docendo.eval.judge.completion") as mock:
            mock.return_value = _litellm_response("[]")
            result = evaluate_answer("", "X", settings=settings)
        assert result.total_claims == 0
        assert result.hallucination_rate == 0.0
