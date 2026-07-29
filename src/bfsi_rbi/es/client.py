"""Elasticsearch client factory."""

from __future__ import annotations

from functools import lru_cache

from elasticsearch import Elasticsearch

from bfsi_rbi.config import Settings, get_settings
from bfsi_rbi.exceptions import ElasticsearchError
from bfsi_rbi.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _build_client(settings_id: str, url: str, api_key: str, timeout: int) -> Elasticsearch:
    """Build a cached Elasticsearch client.

    Args:
        settings_id: Cache-busting identifier (current settings identity).
        url: Elasticsearch URL.
        api_key: Encoded API key.
        timeout: Request timeout in seconds.
    """
    return Elasticsearch(
        hosts=[url],
        api_key=api_key,
        request_timeout=timeout,
        max_retries=3,
        retry_on_timeout=True,
    )


def get_es_client(settings: Settings | None = None) -> Elasticsearch:
    """Return a cached Elasticsearch client."""
    settings = settings or get_settings()
    settings.require_elastic()
    try:
        return _build_client(
            settings_id=id(settings),
            url=settings.elastic_url,
            api_key=settings.elastic_api_key,
            timeout=settings.bfsi_http_timeout,
        )
    except Exception as exc:
        raise ElasticsearchError(f"Failed to build ES client: {exc}") from exc


def ping(settings: Settings | None = None) -> bool:
    """Return True if the cluster is reachable."""
    try:
        client = get_es_client(settings)
        return bool(client.ping())
    except Exception as exc:
        logger.warning("Elasticsearch ping failed: %s", exc)
        return False


__all__ = ["get_es_client", "ping"]
