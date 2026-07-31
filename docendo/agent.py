"""Pydantic AI agent factory.

Builds the ``docendo`` agent. With ``grounded=True`` the agent is attached
to the local retrieval tools (declared in ``retrieval.tools``); with
``grounded=False`` it runs the same agent with no tools, giving us the
ungrounded baseline.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.settings import ModelSettings
from pydantic_ai_litellm import LiteLLMModel  # type: ignore[import-untyped]

from docendo.config import Settings, get_settings
from docendo.logging import get_logger
from docendo.models import Answer

logger = get_logger(__name__)

SYSTEM_PROMPT = """\
You are an expert document analyst for the corpus you have access to.
Answer questions by reading the actual documents.

# Tools

When grounded, you have exactly four tools available:
- search(query, limit): BM25 + semantic hybrid search across the corpus.
- fetch(id): Fetch all chunks of a specific document by ID.
- recent(since, limit): List first-chunk rows since an ISO date.
- compare(id_a, id_b): Side-by-side comparison of two documents.

# Rules

1. Always use the available tools first. Call search to find relevant
   documents. If results are ambiguous, refine with recent or fetch.

2. Cite every factual claim. Each citation must include the circular_id,
   an excerpt (verbatim, <= 400 chars), the source_url, and a one-sentence
   relevance justification.

3. Refuse if out-of-scope. If the corpus does not contain a relevant
   document, set citations=[], confidence='low', and explain in notes.
   Do not invent IDs or paraphrase speculative content.

4. Stay within the current data. Do not extrapolate beyond what a cited
   document explicitly states. If a document has been superseded, note it.

5. Be precise with numbers. Thresholds, dates, and percentages must match
   the cited source exactly.

# Output format

Strictly conform to the Answer schema. The structured output will be
rejected if citations is non-empty but the claims are not supported by
the cited excerpts.
"""


def build(settings: Settings) -> LiteLLMModel:
    """Construct the LiteLLM-backed Pydantic AI model."""
    if not settings.chat_key:
        from docendo.exceptions import ConfigurationError

        raise ConfigurationError("CHAT_KEY is not set.")

    return LiteLLMModel(
        model_name=settings.chat,
        api_key=settings.chat_key,
        api_base=settings.chat_url,
    )


@lru_cache(maxsize=4)
def model(chat_url: str = "", chat_key: str = "", chat_model: str = "") -> LiteLLMModel:
    """One LiteLLMModel per (chat_url, chat_key, chat_model) triple per process.

    Hashable args keep ``lru_cache`` happy; pass the current settings'
    three relevant fields to dedupe by identity.
    """
    if not chat_url and not chat_key and not chat_model:
        s = get_settings()
        chat_url, chat_key, chat_model = s.chat_url, s.chat_key, s.chat
    return LiteLLMModel(
        model_name=f"minimax/{chat_model}" if "/" not in chat_model else chat_model,
        api_key=chat_key,
        api_base=chat_url,
    )


def tools() -> list[Any]:
    """Lazily import and return the four retrieval tool functions."""
    from docendo.retrieval.tools import compare, fetch, recent, search

    return [search, fetch, recent, compare]


def reset() -> None:
    """Clear the cached model (call after env vars change)."""
    model.cache_clear()


def agent(
    grounded: bool = True,
    settings: Settings | None = None,
) -> PydanticAgent[None, Answer]:
    """Build the docendo agent.

    Args:
        grounded: If True, the agent can call the four retrieval tools. If
            False, the agent runs with no tools (ungrounded baseline).
        settings: Optional Settings override; when supplied, a fresh
            LiteLLMModel is built and cached by its three relevant fields.
    """
    if settings is None:
        chat_model = model()
    else:
        chat_model = model(settings.chat_url, settings.chat_key, settings.chat_model)
    tool_list = tools() if grounded else []
    logger.info(
        "Building agent (grounded=%s, tools=%d)",
        grounded,
        len(tool_list),
    )
    return PydanticAgent(
        chat_model,
        output_type=Answer,
        tools=tool_list,
        instructions=SYSTEM_PROMPT,
        model_settings=ModelSettings(temperature=0.0, max_tokens=4096),
        retries=2,
    )


__all__ = ["SYSTEM_PROMPT", "agent", "build", "model", "reset", "tools"]
