"""Evaluation runner: baseline + agent, then judge."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from bfsi_rbi.agent import make_agent
from bfsi_rbi.config import Settings, get_settings
from bfsi_rbi.eval.dataset import EvalCase
from bfsi_rbi.eval.hallucination import HallucinationResult, aevaluate_answer
from bfsi_rbi.logging import get_logger
from bfsi_rbi.models import RBIAnswer

logger = get_logger(__name__)


@dataclass
class CaseResult:
    """Result of running one eval case through both agents."""

    case_name: str
    question: str
    gold_answer: str
    metadata: dict[str, Any] = field(default_factory=dict)
    grounded_answer: str = ""
    grounded_citations: list[dict[str, Any]] = field(default_factory=list)
    grounded_hallucination: HallucinationResult | None = None
    ungrounded_answer: str = ""
    ungrounded_hallucination: HallucinationResult | None = None


def _to_text(answer: RBIAnswer | str) -> str:
    if isinstance(answer, str):
        return answer
    return answer.answer


def _to_citations(answer: RBIAnswer | str) -> list[dict[str, Any]]:
    if isinstance(answer, str):
        return []
    return [c.model_dump(mode="json") for c in answer.citations]


async def _run_one_agent(
    case: EvalCase,
    grounded: bool,
    settings: Settings,
) -> RBIAnswer:
    agent = make_agent(grounded=grounded, settings=settings)
    async with agent:
        result = await agent.run(case.inputs)
    return result.output


async def _run_case(case: EvalCase, settings: Settings) -> CaseResult:
    """Run one case through both grounded and ungrounded agents, then judge."""
    logger.info("Running case %s", case.name)
    grounded_answer, ungrounded_answer = await asyncio.gather(
        _run_one_agent(case, grounded=True, settings=settings),
        _run_one_agent(case, grounded=False, settings=settings),
    )

    grounded_halluc, ungrounded_halluc = await asyncio.gather(
        aevaluate_answer(
            _to_text(grounded_answer),
            case.expected_output,
            settings,
        ),
        aevaluate_answer(
            _to_text(ungrounded_answer),
            case.expected_output,
            settings,
        ),
    )

    return CaseResult(
        case_name=case.name,
        question=case.inputs,
        gold_answer=case.expected_output,
        metadata=case.metadata,
        grounded_answer=_to_text(grounded_answer),
        grounded_citations=_to_citations(grounded_answer),
        grounded_hallucination=grounded_halluc,
        ungrounded_answer=_to_text(ungrounded_answer),
        ungrounded_hallucination=ungrounded_halluc,
    )


def _run_with_concurrency(
    cases: list[EvalCase],
    concurrency: int,
    settings: Settings,
) -> list[CaseResult]:
    """Run cases with a bounded concurrency semaphore."""
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(case: EvalCase) -> CaseResult:
        async with sem:
            return await _run_case(case, settings)

    async def _all() -> list[CaseResult]:
        return await asyncio.gather(*[_bounded(c) for c in cases])

    return asyncio.run(_all())


def run_eval(
    cases: list[EvalCase],
    *,
    concurrency: int | None = None,
    output_path: Path | str | None = None,
    settings: Settings | None = None,
) -> list[CaseResult]:
    """Run the full evaluation suite and return CaseResult list."""
    settings = settings or get_settings()
    settings.require_elastic()
    settings.require_llm()
    concurrency = concurrency or settings.bfsi_eval_concurrency

    logger.info("Running %d cases at concurrency=%d", len(cases), concurrency)
    results = _run_with_concurrency(cases, concurrency, settings)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            for r in results:
                fh.write(json.dumps(_result_to_dict(r)) + "\n")
        logger.info("Wrote %d results to %s", len(results), output_path)

    return results


def _result_to_dict(r: CaseResult) -> dict[str, Any]:
    d = asdict(r)
    # dropped via asdict: nondict hallucination fields. Add manually.
    d["grounded_hallucination"] = (
        r.grounded_hallucination.to_dict() if r.grounded_hallucination else None
    )
    d["ungrounded_hallucination"] = (
        r.ungrounded_hallucination.to_dict() if r.ungrounded_hallucination else None
    )
    return d


__all__ = ["CaseResult", "run_eval"]
