"""``docendo doctor`` — local diagnostics for the SQLite + Qwen3 stack."""

from __future__ import annotations

import asyncio
import sqlite3
import sys
import time
from typing import Any

from docendo.config import Settings, get_settings
from docendo.logging import get_logger

logger = get_logger(__name__)


def _check_sqlite_opens(settings: Settings) -> tuple[bool, str]:
    path = settings.bfsi_sqlite_path
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(path))
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            v = conn.execute("SELECT sqlite_version()").fetchone()[0]
            return True, f"OK (sqlite_version={v})"
        finally:
            conn.close()
    except Exception as exc:
        return False, f"FAIL: {exc}"


def _check_vector_extension(settings: Settings) -> tuple[bool, str]:
    import importlib.resources

    try:
        ext = importlib.resources.files("sqlite_vector.binaries") / "vector"
    except (ModuleNotFoundError, FileNotFoundError) as exc:
        return False, f"FAIL: sqlite_vector binaries not found: {exc}"
    try:
        conn = sqlite3.connect(str(settings.bfsi_sqlite_path))
        try:
            conn.enable_load_extension(True)
            conn.load_extension(str(ext))
            conn.enable_load_extension(False)
            version = conn.execute("SELECT vector_version()").fetchone()[0]
            return True, f"OK (vector_version={version})"
        finally:
            conn.close()
    except Exception as exc:
        return False, f"FAIL: {exc}"


async def _check_embeddings(settings: Settings) -> tuple[bool, str]:
    if not settings.bfsi_embedding_api_key or not settings.bfsi_embedding_api_base:
        return False, "FAIL: BFSI_EMBEDDING_API_KEY/BFSI_EMBEDDING_API_BASE not set"
    try:
        from docendo.retrieval.embeddings import async_embed_texts

        start = time.perf_counter()
        vecs = await async_embed_texts(["ping"], settings=settings)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if not vecs or not vecs[0]:
            return False, "FAIL: embedding returned empty vector"
        return True, f"OK (dim={len(vecs[0])}, elapsed_ms={elapsed_ms:.0f})"
    except Exception as exc:
        return False, f"FAIL: {exc}"


def _check_tokenizer(settings: Settings) -> tuple[bool, str]:
    try:
        from docendo.retrieval import tokenizer

        start = time.perf_counter()
        ids = tokenizer.encode("hello world", settings=settings)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if not ids:
            return False, "FAIL: tokenizer returned empty ids"
        return True, (
            f"OK (model={settings.bfsi_tokenizer_model!r}, "
            f"tokens={len(ids)}, elapsed_ms={elapsed_ms:.1f})"
        )
    except Exception as exc:
        return False, f"FAIL: {exc}"


def _check_minimax(settings: Settings) -> tuple[bool, str]:
    if not settings.minimax_api_key:
        return False, "FAIL: MINIMAX_API_KEY not set"
    return True, f"OK (model={settings.litellm_model}, base={settings.minimax_base_url})"


def _check_tokenizer_match(settings: Settings) -> tuple[bool, str]:
    if settings.bfsi_tokenizer_model == settings.bfsi_embedding_model:
        return True, "OK (match)"
    return False, (
        f"FAIL: tokenizer={settings.bfsi_tokenizer_model!r} != "
        f"embedding={settings.bfsi_embedding_model!r}"
    )


def _check_paths(settings: Settings) -> tuple[bool, str]:
    paths = [
        ("data_raw_dir", settings.data_raw_dir),
        ("data_processed_dir", settings.data_processed_dir),
        ("reports_dir", settings.reports_dir),
        ("eval_dataset_path", settings.eval_dataset_path),
    ]
    bad = []
    for label, p in paths:
        if not p.parent.exists() and label != "eval_dataset_path":
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                bad.append(f"{label}={p}: {exc}")
    if bad:
        return False, "FAIL: " + "; ".join(bad)
    return True, "OK"


async def _run_async_checks(do_embedding: bool, settings: Settings) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    if do_embedding:
        ok, msg = await _check_embeddings(settings)
        results.append(("embeddings", ok, msg))
    return results


def run_doctor(
    *,
    do_embedding: bool = True,
    do_tokenizer: bool = True,
    settings: Settings | None = None,
    stream: Any = None,
) -> int:
    """Run all diagnostic checks; print results; return shell exit code."""
    settings = settings or get_settings()
    out = stream or sys.stdout
    results: list[tuple[str, bool, str]] = []

    # Sync checks first.
    ok, msg = _check_paths(settings)
    results.append(("paths", ok, msg))
    ok, msg = _check_minimax(settings)
    results.append(("minimax_credentials", ok, msg))
    ok, msg = _check_tokenizer_match(settings)
    results.append(("tokenizer_match", ok, msg))
    ok, msg = _check_sqlite_opens(settings)
    results.append(("sqlite_opens", ok, msg))
    ok, msg = _check_vector_extension(settings)
    results.append(("vector_extension", ok, msg))
    if do_tokenizer:
        ok, msg = _check_tokenizer(settings)
        results.append(("tokenizer_load", ok, msg))

    # Async check: live embedding.
    if do_embedding:
        results.extend(asyncio.run(_run_async_checks(True, settings)))

    # Pretty print.
    width = max(len(name) for name, _, _ in results)
    fail_count = 0
    for name, ok, msg in results:
        status = "OK  " if ok else "FAIL"
        out.write(f"  {name:<{width}}  {status}  {msg}\n")
        if not ok:
            fail_count += 1

    out.write("\n")
    if fail_count == 0:
        out.write("All checks passed.\n")
        return 0
    out.write(f"{fail_count} check(s) failed.\n")
    return 1


__all__ = ["run_doctor"]
