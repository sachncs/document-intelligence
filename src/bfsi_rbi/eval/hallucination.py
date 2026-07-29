"""Atomic-claim hallucination evaluator.

Per-question procedure:
1. Split the agent's answer into atomic claims (one fact per claim).
2. For each claim, ask the judge LLM to label it against the gold answer:
   - ``supported``  — explicitly stated in gold
   - ``contradicted`` — directly contradicts gold
   - ``extra``       — plausible but not in gold (counts as hallucination)
3. Aggregate: ``hallucination_rate = (contradicted + extra) / total_claims``.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from litellm import completion
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from bfsi_rbi.config import Settings, get_settings
from bfsi_rbi.logging import get_logger

logger = get_logger(__name__)

ClaimVerdict = Literal["supported", "contradicted", "extra"]


@dataclass
class AtomicClaim:
    """One atomic claim extracted from the agent's answer."""

    text: str
    verdict: ClaimVerdict
    reason: str = ""


@dataclass
class HallucinationResult:
    """Aggregated hallucination score for one answer."""

    claims: list[AtomicClaim] = field(default_factory=list)
    total_claims: int = 0
    supported: int = 0
    contradicted: int = 0
    extra: int = 0

    @property
    def hallucination_rate(self) -> float:
        if self.total_claims == 0:
            return 0.0
        return (self.contradicted + self.extra) / self.total_claims

    @property
    def grounding_score(self) -> float:
        if self.total_claims == 0:
            return 1.0
        return self.supported / self.total_claims

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_claims": self.total_claims,
            "supported": self.supported,
            "contradicted": self.contradicted,
            "extra": self.extra,
            "hallucination_rate": self.hallucination_rate,
            "grounding_score": self.grounding_score,
            "claims": [
                {"text": c.text, "verdict": c.verdict, "reason": c.reason} for c in self.claims
            ],
        }


# ---------------------------------------------------------------------------
# Judge prompts
# ---------------------------------------------------------------------------
_CLAIM_EXTRACTION_PROMPT = """\
You are an evaluation assistant. Given an answer, decompose it into a JSON
array of atomic claims. Each claim must be a single, self-contained, falsifiable
factual statement. Exclude opinions, hedges, and meta-statements.

Answer:
\"\"\"{answer}\"\"\"

Return ONLY a JSON array of strings. Example:
["The capital of France is Paris.", "France is in Europe."]
"""

_CLAIM_JUDGE_PROMPT = """\
You are an evaluation judge. Given an atomic claim and a gold reference
answer, label the claim with one of three verdicts:

- "supported"     — the claim is explicitly stated in the gold answer or
                    follows trivially from it.
- "contradicted"  — the claim directly contradicts the gold answer.
- "extra"         — the claim is plausible but not mentioned in the gold
                    answer (still counts as hallucination for our purposes).

Return ONLY a JSON object with the keys "verdict" and "reason".

Claim: {claim}

Gold answer: {gold}
"""


def _extract_claims(answer: str, settings: Settings) -> list[str]:
    """Use the judge LLM to split an answer into atomic claims."""
    response = completion(
        model=settings.litellm_model,
        api_key=settings.minimax_api_key,
        base_url=settings.minimax_base_url,
        messages=[
            {
                "role": "user",
                "content": _CLAIM_EXTRACTION_PROMPT.format(answer=answer),
            }
        ],
        max_tokens=2000,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to recover: find the first JSON array in the text
        import re

        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            data = {"claims": json.loads(m.group(0))}
        else:
            logger.warning("Could not parse claims JSON: %s", raw[:200])
            return [answer]
    if isinstance(data, list):
        return [str(c) for c in data]
    if "claims" in data and isinstance(data["claims"], list):
        return [str(c) for c in data["claims"]]
    return [answer]


def _judge_claim(claim: str, gold: str, settings: Settings) -> tuple[ClaimVerdict, str]:
    """Judge a single claim against the gold answer."""
    response = completion(
        model=settings.litellm_model,
        api_key=settings.minimax_api_key,
        base_url=settings.minimax_base_url,
        messages=[
            {
                "role": "user",
                "content": _CLAIM_JUDGE_PROMPT.format(claim=claim, gold=gold),
            }
        ],
        max_tokens=200,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "extra", "judge parse failure"
    verdict = data.get("verdict", "extra")
    if verdict not in ("supported", "contradicted", "extra"):
        verdict = "extra"
    return verdict, str(data.get("reason", ""))[:200]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def evaluate_answer(
    answer: str,
    gold: str,
    settings: Settings | None = None,
) -> HallucinationResult:
    """Compute a HallucinationResult for a single (answer, gold) pair."""
    settings = settings or get_settings()
    settings.require_llm()

    claims = _extract_claims(answer, settings)
    if not claims:
        return HallucinationResult()

    verdicts = [_judge_claim(c, gold, settings) for c in claims]
    result = HallucinationResult(total_claims=len(claims))
    for claim, (verdict, reason) in zip(claims, verdicts, strict=True):
        result.claims.append(AtomicClaim(text=claim, verdict=verdict, reason=reason))
        if verdict == "supported":
            result.supported += 1
        elif verdict == "contradicted":
            result.contradicted += 1
        else:
            result.extra += 1
    return result


async def aevaluate_answer(
    answer: str,
    gold: str,
    settings: Settings | None = None,
) -> HallucinationResult:
    """Async variant of :func:`evaluate_answer`."""
    settings = settings or get_settings()
    settings.require_llm()

    claims = await asyncio.to_thread(_extract_claims, answer, settings)
    if not claims:
        return HallucinationResult()

    verdicts = await asyncio.gather(
        *[asyncio.to_thread(_judge_claim, c, gold, settings) for c in claims]
    )

    result = HallucinationResult(total_claims=len(claims))
    for claim, (verdict, reason) in zip(claims, verdicts, strict=True):
        result.claims.append(AtomicClaim(text=claim, verdict=verdict, reason=reason))
        if verdict == "supported":
            result.supported += 1
        elif verdict == "contradicted":
            result.contradicted += 1
        else:
            result.extra += 1
    return result


# ---------------------------------------------------------------------------
# pydantic-evals Adapter
# ---------------------------------------------------------------------------
class AtomicClaimHallucination(Evaluator[Any, Any]):
    """pydantic-evals evaluator that yields per-claim verdicts."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def evaluate(self, ctx: EvaluatorContext[Any, Any]) -> dict[str, float]:
        """Return mapping of metric name → score."""
        answer = str(ctx.output)
        gold = str(ctx.expected_output) if ctx.expected_output is not None else ""
        result = evaluate_answer(answer, gold, settings=self.settings)
        return {
            "grounding_score": result.grounding_score,
            "hallucination_rate": result.hallucination_rate,
        }


__all__ = [
    "AtomicClaim",
    "AtomicClaimHallucination",
    "ClaimVerdict",
    "HallucinationResult",
    "aevaluate_answer",
    "evaluate_answer",
]
