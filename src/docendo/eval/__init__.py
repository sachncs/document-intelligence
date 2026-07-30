"""docendo eval subsystem."""

from docendo.eval.cases import Case, load, save
from docendo.eval.driver import Outcome, run
from docendo.eval.judge import Judge, Verdict, ascore, score
from docendo.eval.summarize import Report, dump, render

__all__ = [
    "Case",
    "Judge",
    "Outcome",
    "Report",
    "Verdict",
    "ascore",
    "dump",
    "load",
    "render",
    "run",
    "save",
    "score",
]
