"""Elasticsearch subsystem."""

from bfsi_rbi.es.client import get_es_client
from bfsi_rbi.es.index import INDEX_MAPPING, INDEX_SETTINGS, ensure_index

__all__ = ["INDEX_MAPPING", "INDEX_SETTINGS", "ensure_index", "get_es_client"]
