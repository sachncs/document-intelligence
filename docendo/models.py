"""Pydantic data models for the agent's structured output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Cite(BaseModel):
    """A single citation pointing to a specific document."""

    circular_id: str = Field(
        description="Document identifier, e.g. 'RBI/2023-24/123' or 'MD.CIR.123'.",
    )
    circular_title: str = Field(
        description="Human-readable title of the cited document.",
    )
    excerpt: str = Field(
        max_length=400,
        description="Verbatim excerpt from the document, max 400 characters.",
    )
    source_url: HttpUrl = Field(
        description="URL where the document can be verified.",
    )
    relevance: str = Field(
        description="One sentence explaining why this citation supports the claim.",
    )


class Answer(BaseModel):
    """Structured, citation-grounded answer."""

    answer: str = Field(
        description=(
            "The grounded answer in professional English. "
            "If the question cannot be answered from the available corpus, "
            "state that explicitly and set confidence='low'."
        ),
    )
    citations: list[Cite] = Field(
        default_factory=list,
        description=(
            "Citations supporting the answer. Must be empty when the answer is a refusal. "
            "Every factual claim must be backed by at least one citation."
        ),
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description=(
            "high = answer directly supported by 1+ cited documents; "
            "medium = partial support or requires inference; "
            "low = insufficient evidence or out-of-scope."
        )
    )
    notes: str | None = Field(
        default=None,
        description="Optional caveat or limitation surfaced to the user.",
    )


class Page(BaseModel):
    """One page of a PDF, with the extraction method used."""

    page_number: int = Field(ge=1)
    text: str
    method: Literal["text", "vision"]
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Self-reported confidence in extracted text (1.0 for pypdf).",
    )


class Record(BaseModel):
    """A full PDF document with structured metadata and pages."""

    circular_id: str
    title: str
    issue_date: str | None = Field(
        default=None,
        description="ISO 8601 issue date (YYYY-MM-DD) parsed from the document.",
    )
    topic: str = Field(default="general")
    source_url: HttpUrl
    pages: list[Page]
    full_text: str = Field(default="", description="Concatenation of all page texts.")

    @model_validator(mode="after")
    def compute_full_text(self) -> Record:
        if not self.full_text and self.pages:
            object.__setattr__(
                self, "full_text", "\n\n".join(p.text for p in self.pages if p.text)
            )
        return self


__all__ = ["Answer", "Cite", "Page", "Record"]
