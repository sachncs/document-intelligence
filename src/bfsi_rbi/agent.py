"""Pydantic AI agent factory.

Builds the ``RBI Policy Analyst`` agent. With ``grounded=True`` the agent is
attached to the local retrieval tools (declared in ``retrieval.tools``); with
``grounded=False`` it runs the same agent with no tools, giving us the
ungrounded baseline.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings
from pydantic_ai_litellm import LiteLLMModel  # type: ignore[import-untyped]

from bfsi_rbi.config import Settings, get_settings
from bfsi_rbi.logging import get_logger
from bfsi_rbi.models import RBIAnswer

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

GRCIT_SYSTEM_PROMPT = """\
You are an expert RBI Policy Analyst. You answer questions about Reserve Bank
of India (RBI) circulars, master directions, and policy documents.

# Tools

When grounded, you have exactly four tools available:
- hybrid_search(query, limit): BM25 + semantic hybrid search across the corpus.
- get_circular(id): Fetch all chunks of a specific circular.
- list_recent(since, limit): List first-chunk rows since an ISO date.
- compare_circulars(id_a, id_b): Side-by-side comparison of two circulars.

# Rules

1. Always use the available tools first. Call hybrid_search to find relevant
   circulars. If results are ambiguous, refine with list_recent or get_circular.

2. Cite every factual claim. Each citation must include the circular_id, an
   excerpt (verbatim, ≤ 400 chars), the source_url on rbi.org.in, and a
   one-sentence relevance justification.

3. Refuse if out-of-scope. If the corpus does not contain a relevant circular,
   set citations=[], confidence='low', and explain in notes. Do not invent
   circular IDs or paraphrase speculative content.

4. Stay within the current data. Do not extrapolate beyond what a cited
   circular explicitly states. If a circular has been superseded, note it.

5. Be precise with numbers. Thresholds, dates, and percentages must match the
   cited source exactly.

# Output format

Strictly conform to the RBIAnswer schema. The structured output will be
rejected if citations is non-empty but the claims are not supported by the
cited excerpts.
"""


def build_litellm_model(settings: Settings) -> LiteLLMModel:
    """Construct the LiteLLM-backed Pydantic AI model."""
    if not settings.minimax_api_key:
        from bfsi_rbi.exceptions import ConfigurationError

        raise ConfigurationError("MINIMAX_API_KEY is not set.")

    return LiteLLMModel(
        model_name=settings.litellm_model,
        api_key=settings.minimax_api_key,
        api_base=settings.minimax_base_url,
    )


@lru_cache(maxsize=1)
def _cached_litellm_model() -> LiteLLMModel:
    """One LiteLLMModel per process; reused across all agent builds."""
    return build_litellm_model(get_settings())


def _tool_functions() -> list[Any]:
    """Lazily import and return the four retrieval tool functions."""
    from bfsi_rbi.retrieval.tools import (
        compare_circulars,
        get_circular,
        hybrid_search,
        list_recent,
    )

    return [hybrid_search, get_circular, list_recent, compare_circulars]


def make_agent(
    grounded: bool = True,
    settings: Settings | None = None,
) -> Agent[None, RBIAnswer]:
    """Build the RBI Policy Analyst agent.

    Args:
        grounded: If True, the agent can call the four retrieval tools. If
            False, the agent runs with no tools (ungrounded baseline).
        settings: Optional Settings override; defaults to the cached singleton.
    """
    _ = settings  # accepted for API compatibility; cached model is the singleton
    model = _cached_litellm_model()
    tools = _tool_functions() if grounded else []
    logger.info(
        "Building agent (grounded=%s, tools=%d)",
        grounded,
        len(tools),
    )
    return Agent(
        model,
        output_type=RBIAnswer,
        tools=tools,
        instructions=GRCIT_SYSTEM_PROMPT,
        model_settings=ModelSettings(temperature=0.0, max_tokens=4096),
        retries=2,
    )


__all__ = ["GRCIT_SYSTEM_PROMPT", "build_litellm_model", "make_agent"]
