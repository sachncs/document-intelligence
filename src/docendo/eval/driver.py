"""Evaluation driver: grounded + ungrounded agents in parallel, then judge.

Both agents share a cached ``LiteLLMModel`` instance. Blocking SQLite calls
inside the tool functions are offloaded to a worker thread via
``asyncio.to_thread`` so the event loop is not stalled.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from docendo.agent import agent
from docendo.config import Settings, get_settings
from docendo.eval.cases import Case
from docendo.eval.judge import Verdict_, ascore
from docendo.logging import get_logger
from docendo.models import Answer

logger = get_logger(__name__)


@dataclass
class Outcome:
    """Result of running one eval case through both agents."""

    case_name: str
    question: str
    gold_answer: str
    metadata: dict[str, Any] = field(default_factory=dict)
    grounded_answer: str = ""
    grounded_citations: list[dict[str, Any]] = field(default_factory=list)
    grounded_hallucination: Verdict_ | None = None
    ungrounded_answer: str = ""
    ungrounded_hallucination: Verdict_ | None = None

    def text(self, answer: Answer | str) -> str:
        if isinstance(answer, str):
            return answer
        return answer.answer

    def citations(self, answer: Answer | str) -> list[dict[str, Any]]:
        if isinstance(answer, str):
            return []
        return [c.model_dump(mode="json") for c in answer.citations]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["grounded_hallucination"] = (
            self.grounded_hallucination.to_dict()
            if self.grounded_hallucination
            else None
        )
        d["ungrounded_hallucination"] = (
            self.ungrounded_hallucination.to_dict()
            if self.ungrounded_hallucination
            else None
        )
        return d


async def run_one(
    case: Case, grounded: bool, settings: Settings
) -> Answer:
    chat_agent = agent(grounded=grounded, settings=settings)
    async with chat_agent:
        result = await chat_agent.run(case.inputs)
    return result.output


async def run_case(case: Case, settings: Settings) -> Outcome:
    """Run one case through both grounded and ungrounded agents, then judge."""
    logger.info("Running case %s", case.name)
    grounded_answer, ungrounded_answer = await asyncio.gather(
        run_one(case, grounded=True, settings=settings),
        run_one(case, grounded=False, settings=settings),
    )

    outcome = Outcome(
        case_name=case.name,
        question=case.inputs,
        gold_answer=case.expected_output,
        metadata=case.metadata,
    )
    outcome.grounded_answer = outcome.text(grounded_answer)
    outcome.grounded_citations = outcome.citations(grounded_answer)
    outcome.ungrounded_answer = outcome.text(ungrounded_answer)

    outcome.grounded_hallucination, outcome.ungrounded_hallucination = await asyncio.gather(
        ascore(outcome.grounded_answer, case.expected_output, settings),
        ascore(outcome.ungrounded_answer, case.expected_output, settings),
    )
    return outcome


def run_bounded(
    cases: list[Case],
    concurrency: int,
    settings: Settings,
) -> list[Outcome]:
    """Run cases with a bounded concurrency semaphore."""
    sem = asyncio.Semaphore(concurrency)

    async def bounded(case: Case) -> Outcome:
        async with sem:
            return await run_case(case, settings)

    async def all_results() -> list[Outcome]:
        return await asyncio.gather(*[bounded(c) for c in cases])

    return asyncio.run(all_results())


def run(
    cases: list[Case],
    *,
    concurrency: int | None = None,
    output_path: Path | str | None = None,
    settings: Settings | None = None,
) -> list[Outcome]:
    """Run the full evaluation suite and return Outcome list."""
    settings = settings or get_settings()
    settings.require_for_run()
    concurrency = concurrency or settings.eval_concurrency

    logger.info("Running %d cases at concurrency=%d", len(cases), concurrency)
    outcomes = run_bounded(cases, concurrency, settings)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            for r in outcomes:
                fh.write(json.dumps(r.to_dict()) + "\n")
        logger.info("Wrote %d results to %s", len(outcomes), output_path)

    return outcomes


__all__ = ["Outcome", "run", "run_bounded", "run_case", "run_one"]
