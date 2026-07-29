"""Standalone script: ensure the ELSER inference endpoint is configured.

Run directly: ``python scripts/setup_inference.py`` or via the CLI as
``bfsi-rbi setup-inference``.
"""

from __future__ import annotations

import httpx

from bfsi_rbi.config import Settings, get_settings
from bfsi_rbi.exceptions import AgentBuilderError
from bfsi_rbi.logging import configure_logging, get_logger

logger = get_logger(__name__)

ELSER_INFERENCE_ID = ".elser-2-elasticsearch"


def ensure_elser(settings: Settings | None = None) -> bool:
    """PUT the ELSER inference endpoint if it doesn't already exist."""
    settings = settings or get_settings()
    settings.require_elastic()
    url = f"{settings.elastic_url.rstrip('/')}/_inference/{ELSER_INFERENCE_ID}"
    headers = {
        "Authorization": f"ApiKey {settings.elastic_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "service": "elasticsearch",
        "service_settings": {
            "model_id": ".elser_model_2",
            "num_allocations": 1,
            "num_threads": 1,
        },
    }
    try:
        with httpx.Client(timeout=settings.bfsi_http_timeout) as client:
            r = client.put(url, headers=headers, json=body)
            if r.status_code in (200, 201):
                logger.info("ELSER inference endpoint created")
                return True
            if r.status_code == 400 and "already_exists" in r.text:
                logger.info("ELSER inference endpoint already exists")
                return True
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise AgentBuilderError(f"Failed to set up ELSER inference: {exc}") from exc
    return False


if __name__ == "__main__":
    configure_logging()
    ensure_elser()
    print("OK")
