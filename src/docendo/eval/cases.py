"""Gold evaluation dataset loader.

Supports YAML (canonical) and JSONL (hand-curated by humans).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class EvalCase(BaseModel):
    """One gold Q/A pair in the evaluation set."""

    name: str
    inputs: str = Field(description="The question posed to the agent.")
    expected_output: str = Field(
        description=(
            "The ground-truth answer, written in the same language/register "
            "the agent should produce. The judge uses this to score claims."
        )
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "topic: factual|procedural|cross_circular|date_bounded|trap; "
            "source_faq_url: optional RBI FAQ URL; "
            "source_circular_ids: list of circular IDs this case grounds."
        ),
    )


def load_dataset(path: Path | str) -> list[EvalCase]:
    """Load gold dataset from YAML or JSONL."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        raw = yaml.safe_load(text) or []
    elif path.suffix.lower() == ".jsonl":
        raw = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif path.suffix.lower() == ".json":
        raw = json.loads(text)
    else:
        raise ValueError(f"Unsupported dataset format: {path.suffix}")

    if not isinstance(raw, list):
        raise ValueError("Dataset must be a list of case objects")
    return [EvalCase(**item) for item in raw]


def save_dataset(cases: list[EvalCase], path: Path | str) -> None:
    """Write the dataset to YAML (canonical)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".yaml", ".yml"}:
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump([c.model_dump() for c in cases], fh, sort_keys=False)
    elif path.suffix.lower() == ".jsonl":
        with path.open("w", encoding="utf-8") as fh:
            for c in cases:
                fh.write(json.dumps(c.model_dump()) + "\n")
    else:
        raise ValueError(f"Unsupported dataset format: {path.suffix}")


__all__ = ["EvalCase", "load_dataset", "save_dataset"]
