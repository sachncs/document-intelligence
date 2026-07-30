"""Tests for the eval dataset loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from docendo.eval.cases import Case, load, save


def sample_cases() -> list[Case]:
    return [
        Case(
            name="kyc_threshold",
            inputs="What is the KYC threshold?",
            expected_output="INR 50,000 for cash transactions.",
            metadata={"topic": "kyc", "year": 2023},
        ),
        Case(
            name="npa_steps",
            inputs="How is NPA classified?",
            expected_output="90+ days overdue.",
            metadata={"topic": "npa"},
        ),
    ]


class TestLoadCases:
    def test_load_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "ds.yaml"
        path.write_text(
            """- name: a
  inputs: Q
  expected_output: A
  metadata: {topic: t}
""",
            encoding="utf-8",
        )
        cases = load(path)
        assert len(cases) == 1
        assert cases[0].name == "a"
        assert cases[0].metadata["topic"] == "t"

    def test_load_jsonl(self, tmp_path: Path) -> None:
        path = tmp_path / "ds.jsonl"
        with path.open("w") as fh:
            fh.write(json.dumps({"name": "a", "inputs": "Q", "expected_output": "A"}) + "\n")
        cases = load(path)
        assert len(cases) == 1

    def test_load_unsupported_format(self, tmp_path: Path) -> None:
        path = tmp_path / "ds.txt"
        path.write_text("x")
        with pytest.raises(ValueError):
            load(path)

    def test_load_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load(tmp_path / "missing.yaml")

    def test_save_and_reload_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "ds.yaml"
        save(sample_cases(), path)
        cases = load(path)
        assert len(cases) == 2
        assert cases[1].name == "npa_steps"
