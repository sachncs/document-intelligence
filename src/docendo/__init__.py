"""docendo: grounded RAG agent for document intelligence."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

try:
    __version__ = package_version("docendo")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.3.0a1"

from docendo.agent import agent as agent
from docendo.config import Settings, get_settings
from docendo.eval.cases import Case as Case
from docendo.eval.driver import Outcome as Outcome
from docendo.eval.judge import Verdict as Verdict
from docendo.eval.summarize import Report as Report
from docendo.ingestion.ingest import Report as IngestReport
from docendo.models import Answer as Answer
from docendo.models import Cite as Cite
from docendo.models import Page as Page
from docendo.models import Record as Record
from docendo.retrieval.store import Store as Store

__all__ = [
    "Answer",
    "Case",
    "Cite",
    "IngestReport",
    "Outcome",
    "Page",
    "Record",
    "Report",
    "Settings",
    "Store",
    "Verdict",
    "__version__",
    "agent",
    "get_settings",
]
