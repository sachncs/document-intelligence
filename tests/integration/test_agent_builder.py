"""Integration tests for Agent Builder deploy.

Marked ``integration`` — skipped unless env is configured.
"""

from __future__ import annotations

import pytest

from bfsi_rbi.agent_builder import deploy_agent, deploy_tools, list_agents, list_tools
from bfsi_rbi.config import Settings

pytestmark = pytest.mark.integration


class TestAgentBuilderDeploy:
    def test_deploy_tools_idempotent(self, settings: Settings) -> None:
        if not settings.elastic_url:
            pytest.skip("No ELASTIC_URL configured")
        results = deploy_tools(settings=settings)
        assert len(results) == 4
        tools = list_tools(settings=settings)
        assert any(t.get("id") == "rbi.hybrid_search" for t in tools)

    def test_deploy_agent_idempotent(self, settings: Settings) -> None:
        if not settings.elastic_url:
            pytest.skip("No ELASTIC_URL configured")
        deploy_agent(settings=settings)
        agents = list_agents(settings=settings)
        assert any(a.get("id") == "rbi-policy-analyst" for a in agents)
