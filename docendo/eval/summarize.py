"""Render a Markdown evaluation report from eval results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from docendo.eval.driver import Outcome


@dataclass
class Report:
    """Aggregate metrics across all cases."""

    outcomes: list[Outcome]
    grounded_hallucination_rate: float = 0.0
    ungrounded_hallucination_rate: float = 0.0
    relative_reduction: float = 0.0
    grounded_avg_grounding_score: float = 0.0
    ungrounded_avg_grounding_score: float = 0.0
    grounded_citation_accuracy: float = 0.0
    by_topic: dict[str, dict[str, float]] = field(default_factory=dict)


def safe_avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate(outcomes: list[Outcome]) -> Report:
    gh = [
        r.grounded_hallucination.hallucination_rate
        for r in outcomes
        if r.grounded_hallucination
    ]
    uh = [
        r.ungrounded_hallucination.hallucination_rate
        for r in outcomes
        if r.ungrounded_hallucination
    ]
    gs = [
        r.grounded_hallucination.grounding_score
        for r in outcomes
        if r.grounded_hallucination
    ]
    us = [
        r.ungrounded_hallucination.grounding_score
        for r in outcomes
        if r.ungrounded_hallucination
    ]

    grounded_rate = safe_avg(gh)
    ungrounded_rate = safe_avg(uh)
    reduction = (
        (ungrounded_rate - grounded_rate) / ungrounded_rate
        if ungrounded_rate > 0
        else 0.0
    )

    cited_outcomes = [r for r in outcomes if r.grounded_citations]
    citation_accuracy = len(cited_outcomes) / len(outcomes) if outcomes else 0.0

    by_topic_raw: dict[str, dict[str, list[float]]] = {}
    for r in outcomes:
        topic = r.metadata.get("topic", "unknown")
        if topic not in by_topic_raw:
            by_topic_raw[topic] = {"grounded": [], "ungrounded": []}
        if r.grounded_hallucination:
            by_topic_raw[topic]["grounded"].append(
                r.grounded_hallucination.hallucination_rate
            )
        if r.ungrounded_hallucination:
            by_topic_raw[topic]["ungrounded"].append(
                r.ungrounded_hallucination.hallucination_rate
            )

    by_topic_summary: dict[str, dict[str, float]] = {
        t: {
            "grounded_hallucination_rate": safe_avg(v["grounded"]),
            "ungrounded_hallucination_rate": safe_avg(v["ungrounded"]),
            "n_cases": float(len(v["grounded"])),
        }
        for t, v in by_topic_raw.items()
    }

    return Report(
        outcomes=outcomes,
        grounded_hallucination_rate=grounded_rate,
        ungrounded_hallucination_rate=ungrounded_rate,
        relative_reduction=reduction,
        grounded_avg_grounding_score=safe_avg(gs),
        ungrounded_avg_grounding_score=safe_avg(us),
        grounded_citation_accuracy=citation_accuracy,
        by_topic=by_topic_summary,
    )


def render_markdown(report: Report) -> str:
    lines: list[str] = []
    lines.append("# docendo Evaluation Report")
    lines.append("")
    lines.append(
        "> Atomic-claim LLM-as-judge evaluation. "
        "Lower hallucination rate = better. Higher grounding score = better."
    )
    lines.append("")
    lines.append("## Aggregate metrics")
    lines.append("")
    lines.append("| Metric | Ungrounded | Grounded | Improvement |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| Hallucination rate | {report.ungrounded_hallucination_rate:.1%} "
        f"| {report.grounded_hallucination_rate:.1%} "
        f"| {report.relative_reduction:+.1%} |"
    )
    lines.append(
        f"| Grounding score | {report.ungrounded_avg_grounding_score:.1%} "
        f"| {report.grounded_avg_grounding_score:.1%} "
        f"| {(report.grounded_avg_grounding_score - report.ungrounded_avg_grounding_score):+.1%} |"
    )
    lines.append(f"| Citation accuracy | n/a | {report.grounded_citation_accuracy:.1%} | n/a |")
    lines.append("")
    lines.append("## By topic")
    lines.append("")
    lines.append("| Topic | Grounded hallu. | Ungrounded hallu. | n |")
    lines.append("|---|---|---|---|")
    for topic, m in sorted(report.by_topic.items()):
        lines.append(
            f"| {topic} | {m['grounded_hallucination_rate']:.1%} "
            f"| {m['ungrounded_hallucination_rate']:.1%} "
            f"| {int(m['n_cases'])} |"
        )
    lines.append("")
    lines.append("## Per-case")
    lines.append("")
    lines.append("| Case | Topic | Grounded H | Ungrounded H | Cited |")
    lines.append("|---|---|---|---|---|")
    for r in report.outcomes:
        gh = r.grounded_hallucination.hallucination_rate if r.grounded_hallucination else 0.0
        uh = r.ungrounded_hallucination.hallucination_rate if r.ungrounded_hallucination else 0.0
        cited = "yes" if r.grounded_citations else "no"
        topic = r.metadata.get("topic", "-")
        lines.append(f"| {r.case_name} | {topic} | {gh:.1%} | {uh:.1%} | {cited} |")
    lines.append("")
    return "\n".join(lines)


def render(outcomes: list[Outcome], output_path: Path | str) -> Report:
    """Compute and write the eval report."""
    report = aggregate(outcomes)
    md = render_markdown(report)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")
    return report


def dump(outcomes: list[Outcome], output_path: Path | str) -> None:
    """Write raw results as JSONL for downstream analysis."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for r in outcomes:
            fh.write(json.dumps(r.to_dict()) + "\n")


__all__ = ["Report", "aggregate", "dump", "render"]
