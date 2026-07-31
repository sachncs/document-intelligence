"""Atomic-claim hallucination evaluator.

Per-question procedure:
1. Split the agent's answer into atomic claims (one fact per claim).
2. For each claim, ask the judge LLM to label it against the gold answer:
   - ``supported``  - explicitly stated in gold
   - ``contradicted`` - directly contradicts gold
   - ``extra``       - plausible but not in gold (counts as hallucination)
3. Aggregate: ``hallucination_rate = (contradicted + extra) / total_claims``.

If the judge LLM fails to parse claims, the answer is treated as a judge
failure (zero claims, zero hallucinations) rather than a single bogus
"extra" claim. This prevents parse failures from biasing the rate.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from litellm import completion
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from docendo.config import Settings, get_settings
from docendo.logging import get_logger

logger = get_logger(__name__)

ClaimVerdict = Literal["supported", "contradicted", "extra"]


@dataclass
class Claim:
    """One atomic claim extracted from the agent's answer."""

    text: str
    verdict: ClaimVerdict
    reason: str = ""


@dataclass
class Verdict:
    """Aggregated hallucination score for one answer."""

    claims: list[Claim] = field(default_factory=list)
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


CLAIM_EXTRACTION_PROMPT = """\
You are an evaluation assistant. Given an answer, decompose it into a JSON
array of atomic claims. Each claim must be a single, self-contained, falsifiable
factual statement. Exclude opinions, hedges, and meta-statements.

Answer:
\"\"\"{answer}\"\"\"

Return ONLY a JSON array of strings. Example:
["The capital of France is Paris.", "France is in Europe."]
"""

CLAIM_JUDGE_PROMPT = """\
You are an evaluation judge. Given an atomic claim and a gold reference
answer, label the claim with one of three verdicts:

- "supported"     - the claim is explicitly stated in the gold answer or
                    follows trivially from it.
- "contradicted"  - the claim directly contradicts the gold answer.
- "extra"         - the claim is plausible but not mentioned in the gold
                    answer (still counts as hallucination for our purposes).

Return ONLY a JSON object with the keys "verdict" and "reason".

Claim: {claim}

Gold answer: {gold}
"""


def extract(answer: str, settings: Settings) -> list[str] | None:
    """Use the judge LLM to split an answer into atomic claims.

    Returns None if the judge output is unparseable. Returning None (not
    ``[answer]``) prevents parse failures from biasing the hallucination rate.
    """
    response = completion(
        model=settings.chat,
        api_key=settings.chat_key,
        api_base=settings.chat_url,
        messages=[
            {
                "role": "user",
                "content": CLAIM_EXTRACTION_PROMPT.format(answer=answer),
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
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            data = {"claims": json.loads(m.group(0))}
        else:
            logger.warning("Could not parse claims JSON: %s", raw[:200])
            return None
    if isinstance(data, list):
        return [str(c) for c in data]
    if "claims" in data and isinstance(data["claims"], list):
        return [str(c) for c in data["claims"]]
    return None


def judge_claim(claim: str, gold: str, settings: Settings) -> tuple[ClaimVerdict, str]:
    """Judge a single claim against the gold answer."""
    response = completion(
        model=settings.chat,
        api_key=settings.chat_key,
        api_base=settings.chat_url,
        messages=[
            {
                "role": "user",
                "content": CLAIM_JUDGE_PROMPT.format(claim=claim, gold=gold),
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
def score(answer: str, gold: str, settings: Settings | None = None) -> Verdict:
    """Compute a Verdict for a single (answer, gold) pair."""
    settings = settings or get_settings()
    settings.require_llm()

    claims = extract(answer, settings)
    if claims is None or not claims:
        # Judge failure: do not bias the rate with a bogus single "extra" claim.
        return Verdict(total_claims=0)

    verdicts = [judge_claim(c, gold, settings) for c in claims]
    result = Verdict(total_claims=len(claims))
    for claim, (verdict, reason) in zip(claims, verdicts, strict=True):
        result.claims.append(Claim(text=claim, verdict=verdict, reason=reason))
        if verdict == "supported":
            result.supported += 1
        elif verdict == "contradicted":
            result.contradicted += 1
        else:
            result.extra += 1
    return result


async def ascore(answer: str, gold: str, settings: Settings | None = None) -> Verdict:
    """Async variant of :func:`score`."""
    settings = settings or get_settings()
    settings.require_llm()

    claims = await asyncio.to_thread(extract, answer, settings)
    if claims is None or not claims:
        return Verdict(total_claims=0)

    verdicts = await asyncio.gather(
        *[asyncio.to_thread(judge_claim, c, gold, settings) for c in claims]
    )

    result = Verdict(total_claims=len(claims))
    for claim, (verdict, reason) in zip(claims, verdicts, strict=True):
        result.claims.append(Claim(text=claim, verdict=verdict, reason=reason))
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
class Judge(Evaluator[Any, Any]):
    """pydantic-evals evaluator that yields per-claim verdicts."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def evaluate(self, ctx: EvaluatorContext[Any, Any]) -> dict[str, float]:
        """Return mapping of metric name -> score."""
        answer = str(ctx.output)
        gold = str(ctx.expected_output) if ctx.expected_output is not None else ""
        result = score(answer, gold, settings=self.settings)
        return {
            "grounding_score": result.grounding_score,
            "hallucination_rate": result.hallucination_rate,
        }


__all__ = [
    "Claim",
    "Judge",
    "Verdict",
    "ascore",
    "extract",
    "judge_claim",
    "score",
]
