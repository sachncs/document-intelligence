"""Index mapping and bootstrap for the ``rbi-circulars`` index."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch

from bfsi_rbi.config import Settings, get_settings
from bfsi_rbi.exceptions import ElasticsearchError
from bfsi_rbi.logging import get_logger

logger = get_logger(__name__)

INDEX_SETTINGS: dict[str, Any] = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "1s",
}

INDEX_MAPPING: dict[str, Any] = {
    "properties": {
        "circular_id": {"type": "keyword"},
        "title": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
        "text": {"type": "text"},
        "semantic_text": {
            "type": "semantic_text",
            "inference_id": ".elser-2-elasticsearch",
        },
        "issue_date": {"type": "date"},
        "topic": {"type": "keyword"},
        "source_url": {"type": "keyword"},
        "page_count": {"type": "integer"},
        "extraction_method": {"type": "keyword"},
    }
}


def ensure_index(
    client: Elasticsearch,
    index_name: str | None = None,
    *,
    recreate: bool = False,
    settings: Settings | None = None,
) -> None:
    """Create the index if missing (or recreate if asked for)."""
    settings = settings or get_settings()
    name = index_name or settings.bfsi_index_name

    try:
        exists = bool(client.indices.exists(index=name))
    except Exception as exc:
        raise ElasticsearchError(f"Failed to check index existence: {exc}") from exc

    if exists and recreate:
        logger.info("Deleting existing index %s", name)
        client.indices.delete(index=name)
        exists = False

    if not exists:
        logger.info("Creating index %s", name)
        try:
            client.indices.create(
                index=name,
                settings=INDEX_SETTINGS,
                mappings=INDEX_MAPPING,
            )
        except Exception as exc:
            raise ElasticsearchError(f"Failed to create index {name}: {exc}") from exc
    else:
        logger.info("Index %s already exists", name)


def delete_index(client: Elasticsearch, index_name: str | None = None) -> None:
    """Delete the index (used by tests)."""
    settings = get_settings()
    name = index_name or settings.bfsi_index_name
    if client.indices.exists(index=name):
        client.indices.delete(index=name)
        logger.info("Deleted index %s", name)


__all__ = ["INDEX_MAPPING", "INDEX_SETTINGS", "delete_index", "ensure_index"]
