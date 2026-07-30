"""Smoke test for the hallucination module (imports)."""

from __future__ import annotations


def test_importable() -> None:
    from docendo.eval.hallucination import (  # noqa: F401
        AtomicClaim,
        AtomicClaimHallucination,
        HallucinationResult,
        aevaluate_answer,
        evaluate_answer,
    )

    assert HallucinationResult([]).total_claims == 0
