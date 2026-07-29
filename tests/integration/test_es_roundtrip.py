"""Integration tests for Elasticsearch roundtrip.

These require a live Elasticsearch cluster. They are marked
``integration`` and skipped unless the env vars are set.
"""

from __future__ import annotations

import pytest

from bfsi_rbi.config import Settings
from bfsi_rbi.es.client import get_es_client, ping
from bfsi_rbi.es.index import ensure_index

pytestmark = pytest.mark.integration


class TestElasticsearchRoundtrip:
    def test_ping(self, settings: Settings) -> None:
        if not settings.elastic_url:
            pytest.skip("No ELASTIC_URL configured")
        assert ping(settings) is True

    def test_ensure_index(self, settings: Settings) -> None:
        if not settings.elastic_url:
            pytest.skip("No ELASTIC_URL configured")
        es = get_es_client(settings)
        test_index = f"{settings.bfsi_index_name}_test"
        try:
            ensure_index(es, test_index, recreate=True, settings=settings)
            assert es.indices.exists(index=test_index)
        finally:
            if es.indices.exists(index=test_index):
                es.indices.delete(index=test_index)
