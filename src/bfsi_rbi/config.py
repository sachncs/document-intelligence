"""Application configuration loaded from environment / .env.

Single source of truth for all runtime knobs. Reads from ``.env`` if present.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator
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

    # --- Local SQLite store ------------------------------------------------
    bfsi_sqlite_path: Path = Field(
        default=Path("data/processed/rbi-circulars.sqlite3"),
        description="Path to the SQLite database file.",
    )

    # --- Embedding provider (Qwen3-matched) --------------------------------
    bfsi_embedding_provider: str = Field(
        default="openai_compatible",
        description=(
            "LiteLLM provider prefix for embeddings. "
            "Use 'openai_compatible' with BFSI_EMBEDDING_API_BASE for Qwen/DashScope/vLLM/etc."
        ),
    )
    bfsi_embedding_model: str = Field(
        default="Qwen/Qwen3-Embedding-8B",
        description="Embedding model id. Must match BFSI_TOKENIZER_MODEL.",
    )
    bfsi_embedding_dims: int = Field(
        default=4096,
        ge=2,
        le=8192,
        description="Embedding vector dimension. Verified at startup by a live probe.",
    )
    bfsi_embedding_api_key: str = Field(
        default="",
        description="API key for the embedding endpoint.",
    )
    bfsi_embedding_api_base: str = Field(
        default="",
        description="Base URL for an OpenAI-compatible /v1/embeddings endpoint.",
    )
    bfsi_embedding_batch_size: int = Field(
        default=64,
        ge=1,
        le=1024,
        description="Maximum number of texts per LiteLLM aembedding call.",
    )

    # --- Tokenizer (must match the embedding model) -----------------------
    bfsi_tokenizer_model: str = Field(
        default="Qwen/Qwen3-Embedding-8B",
        description="HuggingFace model id for the tokenizer. Must match BFSI_EMBEDDING_MODEL.",
    )
    bfsi_allow_tokenizer_mismatch: bool = Field(
        default=False,
        description="If True, allow BFSI_TOKENIZER_MODEL != BFSI_EMBEDDING_MODEL.",
    )

    # --- Chunking (gigatoken tokens) ---------------------------------------
    bfsi_chunk_size_tokens: int = Field(default=384, ge=64, le=8192)
    bfsi_chunk_overlap_tokens: int = Field(default=64, ge=0, le=2048)
    bfsi_max_chars_per_result: int = Field(default=400, ge=50, le=4000)

    # --- Pipeline knobs ----------------------------------------------------
    rbi_fetch_max_docs: int = Field(default=120, ge=1, le=1000)
    bfsi_index_name: str = Field(default="rbi-circulars")
    bfsi_eval_concurrency: int = Field(default=5, ge=1, le=20)
    bfsi_eval_limit: int = Field(default=40, ge=1, le=500)
    bfsi_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    bfsi_http_timeout: int = Field(default=30, ge=5, le=300)
    bfsi_llm_timeout: int = Field(default=60, ge=5, le=600)

    # --- Paths -------------------------------------------------------------
    data_raw_dir: Path = Field(default=Path("data/raw"))
    data_processed_dir: Path = Field(default=Path("data/processed"))
    reports_dir: Path = Field(default=Path("reports"))
    eval_dataset_path: Path = Field(default=Path("eval/dataset.yaml"))

    # --- Internal helpers --------------------------------------------------
    def require_llm(self) -> None:
        """Raise if the LLM provider is not configured."""
        if not self.minimax_api_key:
            raise ConfigurationError(
                "MINIMAX_API_KEY is required for LLM operations. "
                "Set it in .env or pass via env vars."
            )

    def require_embeddings(self) -> None:
        """Raise if the embedding provider is not configured."""
        if not self.bfsi_embedding_api_key or not self.bfsi_embedding_api_base:
            raise ConfigurationError(
                "BFSI_EMBEDDING_API_KEY and BFSI_EMBEDDING_API_BASE are required for "
                "embeddings. Configure the OpenAI-compatible Qwen endpoint in .env."
            )

    def require_for_run(self) -> None:
        """Raise if any of the runtime knobs the selected backend needs are missing."""
        self.require_llm()
        self.require_embeddings()

    def validate_tokenizer_match(self) -> None:
        """Refuse to run when the embedding model id differs from the tokenizer id."""
        if (
            self.bfsi_tokenizer_model != self.bfsi_embedding_model
            and not self.bfsi_allow_tokenizer_mismatch
        ):
            raise ConfigurationError(
                f"BFSI_TOKENIZER_MODEL={self.bfsi_tokenizer_model!r} does not match "
                f"BFSI_EMBEDDING_MODEL={self.bfsi_embedding_model!r}. "
                "Set BFSI_ALLOW_TOKENIZER_MISMATCH=1 to override, or align the values."
            )

    @model_validator(mode="after")
    def _validate_chunk_overlap(self) -> Settings:
        if self.bfsi_chunk_overlap_tokens >= self.bfsi_chunk_size_tokens:
            raise ConfigurationError(
                "BFSI_CHUNK_OVERLAP_TOKENS must be strictly less than BFSI_CHUNK_SIZE_TOKENS."
            )
        return self

    @property
    def litellm_model(self) -> str:
        """LiteLLM provider-prefixed model name for the chat LLM."""
        return f"minimax/{self.minimax_model}"

    @property
    def litellm_embedding_model(self) -> str:
        """LiteLLM provider-prefixed model name for the embedding model."""
        provider = self.bfsi_embedding_provider
        model = self.bfsi_embedding_model
        if "/" in model:
            return model
        return f"{provider}/{model}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings loader."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear the lru_cache so env changes are picked up by tests."""
    get_settings.cache_clear()


def probe_embedding_dim(
    settings: Settings | None = None,
    *,
    timeout: float = 10.0,
) -> int:
    """Issue one live embedding call to verify the configured model and dimension.

    Returns the observed embedding length. Raises ``ConfigurationError`` on
    network/credential failures or when the observed dimension does not match
    ``BFSI_EMBEDDING_DIMS``.
    """
    import asyncio

    import litellm

    settings = settings or get_settings()
    settings.validate_tokenizer_match()
    settings.require_embeddings()

    api_base = settings.bfsi_embedding_api_base.rstrip("/")
    if not api_base.endswith("/v1"):
        api_base = f"{api_base}/v1"

    async def _probe() -> Any:
        return await litellm.aembedding(
            model=settings.litellm_embedding_model,
            input=["dimension probe"],
            api_key=settings.bfsi_embedding_api_key,
            api_base=api_base,
            timeout=timeout,
        )

    try:
        resp = asyncio.run(_probe())
    except Exception as exc:
        raise ConfigurationError(
            f"Embedding probe failed for {settings.litellm_embedding_model!r} at "
            f"{api_base!r}: {exc}. Check BFSI_EMBEDDING_API_KEY, BFSI_EMBEDDING_API_BASE, "
            "and the model id."
        ) from exc

    try:
        observed = len(resp.data[0]["embedding"])
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise ConfigurationError(
            f"Embedding probe returned an unexpected payload: {resp!r}"
        ) from exc

    if observed != settings.bfsi_embedding_dims:
        raise ConfigurationError(
            f"Embedding probe dimension {observed} does not match "
            f"BFSI_EMBEDDING_DIMS={settings.bfsi_embedding_dims}. "
            "Update BFSI_EMBEDDING_DIMS to the observed value."
        )
    return observed


__all__ = ["Settings", "get_settings", "probe_embedding_dim", "reset_settings_cache"]
