"""Streamlit A/B chat UI.

Run with: ``docendo demo`` (defaults to http://localhost:8501).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any

import streamlit as st

from docendo.agent import agent as build_agent
from docendo.config import get_settings
from docendo.eval.cases import load as load_cases
from docendo.eval.judge import ascore
from docendo.logging import get_logger
from docendo.models import Answer

logger = get_logger(__name__)


@st.cache_resource
def build_agents() -> tuple[Any, Any]:
    """Build both agents once and cache them across reruns."""
    settings = get_settings()
    return (
        build_agent(grounded=True, settings=settings),
        build_agent(grounded=False, settings=settings),
    )


@st.cache_resource
def executor() -> concurrent.futures.ThreadPoolExecutor:
    """Dedicated worker pool so async work runs on its own event loop."""
    return concurrent.futures.ThreadPoolExecutor(max_workers=2)


@st.cache_data
def load_questions() -> list[dict[str, Any]]:
    """Load the gold dataset and surface the questions."""
    settings = get_settings()
    items = load_cases(settings.eval_dataset_path)
    return [
        {
            "name": c.name,
            "topic": c.metadata.get("topic", "general"),
            "inputs": c.inputs,
        }
        for c in items
    ]


async def ask(chat_agent: Any, question: str) -> Answer:
    async with chat_agent:
        result = await chat_agent.run(question)
    return result.output  # type: ignore[no-any-return]


async def grade(answer: str, gold: str) -> dict[str, Any]:
    if not gold:
        return {"hallucination_rate": 0.0, "grounding_score": 1.0, "claims": []}
    result = await ascore(answer, gold, get_settings())
    return result.to_dict()


def run_async(coro: Any) -> Any:
    """Run ``coro`` to completion on a worker-thread event loop."""
    ex = executor()

    def runner() -> Any:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    future = ex.submit(runner)
    return future.result()


def render(col: Any, label: str, answer: Answer, halluc: dict[str, Any]) -> None:
    with col:
        st.subheader(label)
        st.markdown(answer.answer)
        if answer.citations:
            st.markdown("**Citations**")
            for c in answer.citations:
                st.markdown(f"- [{c.circular_id}]({c.source_url}) - *{c.circular_title}*")
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
        page_title="docendo A/B",
        page_icon="📜",
        layout="wide",
    )
    st.title("docendo A/B Demo")
    st.caption(
        "Grounded (left) vs ungrounded (right). Both use the same chat model; "
        "the grounded agent has access to four local SQLite retrieval tools."
    )

    questions = load_questions()
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

    grounded_chat_agent, ungrounded_chat_agent = build_agents()

    with st.spinner("Running both agents in parallel..."):
        grounded_out, ungrounded_out = run_async(
            asyncio.gather(
                ask(grounded_chat_agent, question),
                ask(ungrounded_chat_agent, question),
            )
        )

    items = load_cases(get_settings().eval_dataset_path)
    gold = next((c.expected_output for c in items if c.name == choice), "")

    with st.spinner("Judging answers..."):
        g_halluc, u_halluc = run_async(
            asyncio.gather(
                grade(grounded_out.answer, gold),
                grade(ungrounded_out.answer, gold),
            )
        )

    col_g, col_u = st.columns(2)
    render(col_g, "Grounded", grounded_out, g_halluc)
    render(col_u, "Ungrounded", ungrounded_out, u_halluc)

    delta = u_halluc["hallucination_rate"] - g_halluc["hallucination_rate"]
    st.divider()
    st.markdown(
        f"**Hallucination delta:** grounded is **{delta:.1%}** lower than ungrounded  "
        f"({g_halluc['hallucination_rate']:.1%} vs {u_halluc['hallucination_rate']:.1%})."
    )


if __name__ == "__main__":
    main()
