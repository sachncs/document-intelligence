"""Evaluation subsystem."""

from docendo.eval.dataset import EvalCase, load_dataset
from docendo.eval.hallucination import (
    AtomicClaim,
    AtomicClaimHallucination,
    ClaimVerdict,
    HallucinationResult,
)
from docendo.eval.report import EvalReport, generate_report
from docendo.eval.runner import CaseResult, run_eval

__all__ = [
    "AtomicClaim",
    "AtomicClaimHallucination",
    "CaseResult",
    "ClaimVerdict",
    "EvalCase",
    "EvalReport",
    "HallucinationResult",
    "generate_report",
    "load_dataset",
    "run_eval",
]
