"""Tests for the tool specs module."""

from __future__ import annotations

from bfsi_rbi.agent_builder.specs import (
    AGENT_SPEC,
    TOOL_SPECS,
    compare_circulars_tool,
    get_circular_tool,
    hybrid_search_tool,
    list_recent_tool,
)


class TestToolSpecs:
    def test_all_have_required_keys(self) -> None:
        for spec in TOOL_SPECS:
            assert spec["id"].startswith("rbi.")
            assert spec["type"] == "esql"
            assert "description" in spec
            assert "configuration" in spec
            assert "query" in spec["configuration"]
            assert "params" in spec["configuration"]

    def test_hybrid_uses_fork_fuse(self) -> None:
        assert "FORK" in hybrid_search_tool["configuration"]["query"]
        assert "FUSE RRF" in hybrid_search_tool["configuration"]["query"]

    def test_get_circular_filters_by_id(self) -> None:
        assert "circular_id" in get_circular_tool["configuration"]["query"]

    def test_list_recent_has_date_param(self) -> None:
        params = list_recent_tool["configuration"]["params"]
        assert params["since"]["type"] == "date"

    def test_compare_circulars_takes_two_ids(self) -> None:
        params = compare_circulars_tool["configuration"]["params"]
        assert "id_a" in params and "id_b" in params

    def test_agent_spec_references_all_tools(self) -> None:
        tool_ids = AGENT_SPEC["configuration"]["tools"][0]["tool_ids"]
        assert set(tool_ids) == {t["id"] for t in TOOL_SPECS}
