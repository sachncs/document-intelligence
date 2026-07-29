"""Application configuration loaded from environment / .env.

Single source of truth for all runtime knobs. Reads from ``.env`` if present.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bfsi_rbi.exceptions import ConfigurationError


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="",
    )

    # --- MiniMax (LLM) -----------------------------------------------------
    minimax_base_url: str = Field(
        default="https://api.minimax.io/v1",
        description="OpenAI-compatible base URL for MiniMax.",
    )
    minimax_api_key: str = Field(
        default="",
        description="MiniMax API key. May be empty during local index builds.",
    )
    minimax_model: str = Field(
        default="MiniMax-M3",
        description="MiniMax model name (LiteLLM provider: minimax/<name>).",
    )

    # --- Elastic Cloud -----------------------------------------------------
    elastic_url: str = Field(
        default="",
        description="Elasticsearch deployment URL (no trailing slash).",
    )
    elastic_api_key: str = Field(
        default="",
        description="Encoded Elastic API key.",
    )
    elastic_mcp_url: str = Field(
        default="",
        description="MCP endpoint exposed by Agent Builder.",
    )

    # --- Pipeline knobs ----------------------------------------------------
    rbi_fetch_max_docs: int = Field(default=120, ge=1, le=1000)
    bfsi_index_name: str = Field(default="rbi-circulars")
    bfsi_chunk_size: int = Field(default=1500, ge=100, le=8000)
    bfsi_chunk_overlap: int = Field(default=200, ge=0, le=2000)
    bfsi_eval_concurrency: int = Field(default=5, ge=1, le=20)
    bfsi_eval_limit: int = Field(default=40, ge=1, le=500)
    bfsi_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    bfsi_http_timeout: int = Field(default=30, ge=5, le=300)

    # --- Paths -------------------------------------------------------------
    data_raw_dir: Path = Field(default=Path("data/raw"))
    data_processed_dir: Path = Field(default=Path("data/processed"))
    reports_dir: Path = Field(default=Path("reports"))
    eval_dataset_path: Path = Field(default=Path("eval/dataset.yaml"))

    # --- Internal helpers ---------------------------------------------------
    @field_validator("elastic_mcp_url")
    @classmethod
    def _ensure_mcp_suffix(cls, v: str, info: object) -> str:
        if v:
            return v
        url = getattr(info, "data", {}).get("elastic_url", "")
        if url and not url.endswith("/api/agent_builder/mcp"):
            return f"{url.rstrip('/')}/api/agent_builder/mcp"
        return v

    def require_llm(self) -> None:
        """Raise if the LLM provider is not configured."""
        if not self.minimax_api_key:
            raise ConfigurationError(
                "MINIMAX_API_KEY is required for LLM operations. "
                "Set it in .env or pass via env vars."
            )

    def require_elastic(self) -> None:
        """Raise if Elasticsearch is not configured."""
        if not self.elastic_url or not self.elastic_api_key:
            raise ConfigurationError(
                "ELASTIC_URL and ELASTIC_API_KEY are required for Elasticsearch operations. "
                "Set them in .env or pass via env vars."
            )

    @property
    def litellm_model(self) -> str:
        """LiteLLM provider-prefixed model name."""
        return f"minimax/{self.minimax_model}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings loader."""
    return Settings()
