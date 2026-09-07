"""Unit test for the docendo public root exports."""

from __future__ import annotations

import docendo
from docendo import agent as agent_fn
from docendo.config import get_settings


class TestRootExports:
    def test_version_present(self) -> None:
        assert isinstance(docendo.__version__, str)
        assert docendo.__version__ == "0.3.0a1"

    def test_documented_symbols_present(self) -> None:
        for name in (
            "agent",
            "Answer",
            "Case",
            "Cite",
            "IngestReport",
            "Outcome",
            "Page",
            "Record",
            "Report",
            "Settings",
            "Store",
            "Verdict",
            "get_settings",
        ):
            assert hasattr(docendo, name), f"{name} missing from docendo root"

    def test_no_internal_modules_leaked(self) -> None:
        """The single-underscore `_internal` module must NOT be re-exported
        from the root."""
        assert not hasattr(docendo, "_internal")

    def test_agent_callable(self) -> None:
        # agent is a factory; just confirm it's callable from the root.
        assert callable(agent_fn)

    def test_get_settings_callable_from_root(self) -> None:
        s = get_settings()
        assert s is docendo.get_settings()
