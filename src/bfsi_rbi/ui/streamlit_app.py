"""Streamlit A/B chat UI for the RBI Policy Analyst.

Run with: ``bfsi-rbi demo`` (defaults to http://localhost:8501).
"""

from __future__ import annotations

import asyncio
from typing import Any

import streamlit as st

from bfsi_rbi.agent import make_agent
from bfsi_rbi.config import get_settings
from bfsi_rbi.eval.dataset import load_dataset
from bfsi_rbi.eval.hallucination import aevaluate_answer
from bfsi_rbi.logging import get_logger
from bfsi_rbi.models import RBIAnswer

logger = get_logger(__name__)


@st.cache_resource
def _cached_agents() -> tuple[Any, Any]:
    """Build both agents once and cache them across reruns."""
    settings = get_settings()
    return (
        make_agent(grounded=True, settings=settings),
        make_agent(grounded=False, settings=settings),
    )


@st.cache_data
def _load_eval_questions() -> list[dict[str, Any]]:
    """Load the gold dataset and surface the questions."""
    settings = get_settings()
    cases = load_dataset(settings.eval_dataset_path)
    return [
        {
            "name": c.name,
            "topic": c.metadata.get("topic", "general"),
            "inputs": c.inputs,
        }
        for c in cases
    ]


async def _run_agent(agent: Any, question: str) -> RBIAnswer:
    async with agent:
        result = await agent.run(question)
    return result.output  # type: ignore[no-any-return]


async def _judge(answer: str, gold: str) -> dict[str, Any]:
    if not gold:
        return {"hallucination_rate": 0.0, "grounding_score": 1.0, "claims": []}
    result = await aevaluate_answer(answer, gold, get_settings())
    return result.to_dict()


def _render_answer_col(col: Any, label: str, answer: RBIAnswer, halluc: dict[str, Any]) -> None:
    with col:
        st.subheader(label)
        st.markdown(answer.answer)
        if answer.citations:
            st.markdown("**Citations**")
            for c in answer.citations:
                st.markdown(f"- [{c.circular_id}]({c.source_url}) — *{c.circular_title}*")
                st.caption(f"> {c.excerpt}")
                st.caption(f"_{c.relevance}_")
        if answer.notes:
            st.info(answer.notes)
        st.caption(
            f"Confidence: **{answer.confidence}** · "
            f"Hallucination rate: **{halluc['hallucination_rate']:.1%}** "
            f"({halluc['total_claims']} claims)"
        )


def main() -> None:
    st.set_page_config(
        page_title="RBI Policy Analyst — A/B",
        page_icon="📜",
        layout="wide",
    )
    st.title("RBI Policy Analyst — A/B Demo")
    st.caption(
        "Grounded (left) vs ungrounded (right). Both use the same MiniMax-M3 model; "
        "only the Agent Builder MCP tools differ."
    )

    questions = _load_eval_questions()
    topics = sorted({q["topic"] for q in questions})
    selected_topic = st.sidebar.selectbox("Topic filter", ["all", *topics])
    if selected_topic != "all":
        pool = [q for q in questions if q["topic"] == selected_topic]
    else:
        pool = questions

    if not pool:
        st.warning("No questions match this filter.")
        return

    choice = st.sidebar.selectbox(
        "Sample question",
        options=[q["name"] for q in pool],
        format_func=lambda n: n,
    )
    sample = next(q for q in pool if q["name"] == choice)
    question = st.text_area("Question", value=sample["inputs"], height=80)

    if not st.button("Run A/B"):
        st.stop()

    grounded_agent, ungrounded_agent = _cached_agents()

    with st.spinner("Running both agents in parallel..."):
        result_pair: tuple[RBIAnswer, RBIAnswer] = asyncio.run(
            asyncio.gather(
                _run_agent(grounded_agent, question),
                _run_agent(ungrounded_agent, question),
            )  # type: ignore[arg-type]
        )
        grounded_out: RBIAnswer = result_pair[0]
        ungrounded_out: RBIAnswer = result_pair[1]

    # Re-judge against the gold answer if available
    cases = load_dataset(get_settings().eval_dataset_path)
    gold = next((c.expected_output for c in cases if c.name == choice), "")

    with st.spinner("Judging answers..."):
        halluc_pair: tuple[dict[str, Any], dict[str, Any]] = asyncio.run(
            asyncio.gather(
                _judge(grounded_out.answer, gold),
                _judge(ungrounded_out.answer, gold),
            )  # type: ignore[arg-type]
        )
        g_halluc: dict[str, Any] = halluc_pair[0]
        u_halluc: dict[str, Any] = halluc_pair[1]

    col_g, col_u = st.columns(2)
    _render_answer_col(col_g, "Grounded", grounded_out, g_halluc)
    _render_answer_col(col_u, "Ungrounded", ungrounded_out, u_halluc)

    # Delta summary
    delta = u_halluc["hallucination_rate"] - g_halluc["hallucination_rate"]
    st.divider()
    st.markdown(
        f"**Hallucination delta:** grounded is **{delta:.1%}** lower than ungrounded  "
        f"({g_halluc['hallucination_rate']:.1%} vs {u_halluc['hallucination_rate']:.1%})."
    )


if __name__ == "__main__":
    main()
