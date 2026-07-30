"""Application configuration loaded from environment / .env.

Single source of truth for all runtime knobs. Reads from ``.env`` if present.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from docendo.exceptions import ConfigurationError


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="",
    )

    # --- Chat (LLM) -----------------------------------------------------
    chat_url: str = Field(
        default="https://api.minimax.io/v1",
        description="OpenAI-compatible base URL for the chat model.",
    )
    chat_key: str = Field(
        default="",
        description="Chat model API key. May be empty during local index builds.",
    )
    chat_model: str = Field(
        default="MiniMax-M3",
        description="Chat model name (LiteLLM provider prefix is added by Settings.chat).",
    )
    chat_timeout: int = Field(default=60, ge=5, le=600)

    # --- Local SQLite store ------------------------------------------------
    store_path: Path = Field(
        default=Path("data/processed/docendo.sqlite3"),
        description="Path to the SQLite database file.",
    )

    # --- Embedding provider (Qwen3-matched) --------------------------------
    vector_provider: str = Field(
        default="openai_compatible",
        description=(
            "LiteLLM provider prefix for embeddings. "
            "Use 'openai_compatible' with VECTOR_BASE for Qwen/DashScope/vLLM/etc."
        ),
    )
    vector_model: str = Field(
        default="Qwen/Qwen3-Embedding-8B",
        description="Embedding model id. Must match TOKENIZER_MODEL.",
    )
    vector_dims: int = Field(
        default=4096,
        ge=2,
        le=8192,
        description="Embedding vector dimension. Verified at startup by a live probe.",
    )
    vector_key: str = Field(
        default="",
        description="API key for the embedding endpoint.",
    )
    vector_base: str = Field(
        default="",
        description="Base URL for an OpenAI-compatible /v1/embeddings endpoint.",
    )
    vector_batch: int = Field(
        default=64,
        ge=1,
        le=1024,
        description="Maximum number of texts per LiteLLM aembedding call.",
    )

    # --- Tokenizer (must match the embedding model) -----------------------
    tokenizer_model: str = Field(
        default="Qwen/Qwen3-Embedding-8B",
        description="HuggingFace model id for the tokenizer. Must match VECTOR_MODEL.",
    )
    tokenizer_allow_mismatch: bool = Field(
        default=False,
        description="If True, allow TOKENIZER_MODEL != VECTOR_MODEL.",
    )

    # --- Chunking (gigatoken tokens) ---------------------------------------
    chunk_size: int = Field(default=384, ge=64, le=8192)
    chunk_overlap: int = Field(default=64, ge=0, le=2048)
    chunk_max_chars: int = Field(default=400, ge=50, le=4000)

    # --- Retrieval --------------------------------------------------------
    rrf_k: int = Field(default=60, ge=1, le=1000)

    # --- Pipeline knobs ----------------------------------------------------
    fetch_max_docs: int = Field(default=120, ge=1, le=1000)
    eval_concurrency: int = Field(default=5, ge=1, le=20)
    eval_limit: int = Field(default=40, ge=1, le=500)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    http_timeout: int = Field(default=30, ge=5, le=300)

    # --- Paths -------------------------------------------------------------
    data_raw_dir: Path = Field(default=Path("data/raw"))
    data_processed_dir: Path = Field(default=Path("data/processed"))
    reports_dir: Path = Field(default=Path("reports"))
    eval_dataset_path: Path = Field(default=Path("eval/cases.yaml"))

    # --- Internal helpers --------------------------------------------------
    def require_llm(self) -> None:
        """Raise if the chat model is not configured."""
        if not self.chat_key:
            raise ConfigurationError(
                "CHAT_KEY is required for LLM operations. "
                "Set it in .env or pass via env vars."
            )

    def require_embeddings(self) -> None:
        """Raise if the embedding provider is not configured."""
        if not self.vector_key or not self.vector_base:
            raise ConfigurationError(
                "VECTOR_KEY and VECTOR_BASE are required for embeddings. "
                "Configure the OpenAI-compatible Qwen endpoint in .env."
            )

    def require_for_run(self) -> None:
        """Raise if any of the runtime knobs the selected backend needs are missing."""
        self.require_llm()
        self.require_embeddings()

    def validate_tokenizer_match(self) -> None:
        """Refuse to run when the embedding model id differs from the tokenizer id."""
        if (
            self.tokenizer_model != self.vector_model
            and not self.tokenizer_allow_mismatch
        ):
            raise ConfigurationError(
                f"TOKENIZER_MODEL={self.tokenizer_model!r} does not match "
                f"VECTOR_MODEL={self.vector_model!r}. "
                "Set TOKENIZER_ALLOW_MISMATCH=1 to override, or align the values."
            )

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> Settings:
        if self.chunk_overlap >= self.chunk_size:
            raise ConfigurationError(
                "CHUNK_OVERLAP must be strictly less than CHUNK_SIZE."
            )
        return self

    @property
    def chat(self) -> str:
        """LiteLLM provider-prefixed chat model id."""
        return f"minimax/{self.chat_model}"

    @property
    def vector_id(self) -> str:
        """LiteLLM provider-prefixed embedding model id."""
        model = self.vector_model
        if "/" in model:
            return model
        return f"{self.vector_provider}/{model}"


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
    ``VECTOR_DIMS``.
    """
    import asyncio

    import litellm

    settings = settings or get_settings()
    settings.validate_tokenizer_match()
    settings.require_embeddings()

    api_base = settings.vector_base.rstrip("/")
    if not api_base.endswith("/v1"):
        api_base = f"{api_base}/v1"

    async def _probe() -> Any:
        return await litellm.aembedding(
            model=settings.vector_id,
            input=["dimension probe"],
            api_key=settings.vector_key,
            api_base=api_base,
            timeout=timeout,
        )

    try:
        resp = asyncio.run(_probe())
    except Exception as exc:
        raise ConfigurationError(
            f"Embedding probe failed for {settings.vector_id!r} at "
            f"{api_base!r}: {exc}. Check VECTOR_KEY, VECTOR_BASE, and the model id."
        ) from exc

    try:
        observed = len(resp.data[0]["embedding"])
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise ConfigurationError(
            f"Embedding probe returned an unexpected payload: {resp!r}"
        ) from exc

    if observed != settings.vector_dims:
        raise ConfigurationError(
            f"Embedding probe dimension {observed} does not match "
            f"VECTOR_DIMS={settings.vector_dims}. "
            "Update VECTOR_DIMS to the observed value."
        )
    return observed


__all__ = ["Settings", "get_settings", "probe_embedding_dim", "reset_settings_cache"]
