"""Evaluation subsystem."""

from bfsi_rbi.eval.dataset import EvalCase, load_dataset
from bfsi_rbi.eval.hallucination import (
    AtomicClaim,
    AtomicClaimHallucination,
    ClaimVerdict,
    HallucinationResult,
)
from bfsi_rbi.eval.report import EvalReport, generate_report
from bfsi_rbi.eval.runner import CaseResult, run_eval

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
