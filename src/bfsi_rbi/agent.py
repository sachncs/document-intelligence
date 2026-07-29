"""Pydantic AI agent factory.

Builds the ``RBI Policy Analyst`` agent. The agent is grounded via the
Agent Builder MCP server when ``grounded=True``; with ``grounded=False`` it
runs the same agent with no tools, giving us the ungrounded baseline.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.capabilities import MCP
from pydantic_ai.settings import ModelSettings
from pydantic_ai_litellm import LiteLLMModel  # type: ignore[import-untyped]

from bfsi_rbi.config import Settings, get_settings
from bfsi_rbi.logging import get_logger
from bfsi_rbi.models import RBIAnswer

logger = get_logger(__name__)

GRCIT_SYSTEM_PROMPT = """\
You are an expert RBI Policy Analyst. You answer questions about Reserve Bank
of India (RBI) circulars, master directions, and policy documents.

# Rules

1. **Always use the available tools first.** Before answering, call
   `rbi.hybrid_search` to find relevant circulars. If results are
   ambiguous, refine with `rbi.list_recent` or `rbi.get_circular`.

2. **Cite every factual claim.** Each citation must include the
   `circular_id`, an `excerpt` (verbatim, ≤ 400 chars), the `source_url` on
   rbi.org.in, and a one-sentence `relevance` justification.

3. **Refuse if out-of-scope.** If the corpus does not contain a relevant
   circular, set `citations=[]`, `confidence='low'`, and explain in `notes`.
   Do not invent circular IDs or paraphrase speculative content.

4. **Stay within the current data.** Do not extrapolate beyond what a cited
   circular explicitly states. If a circular has been superseded, note it.

5. **Be precise with numbers.** Thresholds, dates, and percentages must
   match the cited source exactly.

# Output format

Strictly conform to the `RBIAnswer` schema. The structured output will
be rejected if `citations` is non-empty but the claims are not supported
by the cited excerpts.
"""


def build_litellm_model(settings: Settings) -> LiteLLMModel:
    """Construct the LiteLLM-backed Pydantic AI model."""
    if not settings.minimax_api_key:
        from bfsi_rbi.exceptions import ConfigurationError

        raise ConfigurationError("MINIMAX_API_KEY is not set.")

    return LiteLLMModel(
        model_name=settings.litellm_model,
        api_key=settings.minimax_api_key,
        base_url=settings.minimax_base_url,
    )


def make_agent(
    grounded: bool = True,
    settings: Settings | None = None,
) -> Agent[None, RBIAnswer]:
    """Build the RBI Policy Analyst agent.

    Args:
        grounded: If True, the agent can call Agent Builder MCP tools.
            If False, the agent runs with no tools (ungrounded baseline).
        settings: Optional Settings override; defaults to the cached singleton.

    Returns:
        A configured Pydantic AI Agent producing ``RBIAnswer``.
    """
    settings = settings or get_settings()
    model = build_litellm_model(settings)

    capabilities: list[MCP] = []
    if grounded:
        if not settings.elastic_mcp_url:
            from bfsi_rbi.exceptions import ConfigurationError

            raise ConfigurationError("ELASTIC_MCP_URL is not set; cannot enable grounded mode.")
        capabilities.append(MCP(url=settings.elastic_mcp_url))
        logger.info("Building GROUNDED agent (MCP tools enabled)")
    else:
        logger.info("Building UNGROUNDED agent (no tools)")

    return Agent(
        model,
        output_type=RBIAnswer,
        capabilities=capabilities,
        instructions=GRCIT_SYSTEM_PROMPT,
        model_settings=ModelSettings(temperature=0.0, max_tokens=4096),
        retries=2,
    )


__all__ = ["GRCIT_SYSTEM_PROMPT", "build_litellm_model", "make_agent"]
