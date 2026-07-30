"""``docendo checkup`` - local diagnostics for the SQLite + Qwen3 stack."""

from __future__ import annotations

import asyncio
import importlib.resources
import sqlite3
import time
from typing import Any

from docendo.config import Settings, get_settings
from docendo.logging import get_logger

logger = get_logger(__name__)


def paths(settings: Settings) -> tuple[bool, str]:
    for label, p in (
        ("data_raw_dir", settings.data_raw_dir),
        ("data_processed_dir", settings.data_processed_dir),
        ("reports_dir", settings.reports_dir),
    ):
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"FAIL: {label}={p}: {exc}"
    return True, "OK"


def chat_creds(settings: Settings) -> tuple[bool, str]:
    if not settings.chat_key:
        return False, "FAIL: CHAT_KEY not set"
    return True, f"OK (model={settings.chat}, base={settings.chat_url})"


def tokenizer_match(settings: Settings) -> tuple[bool, str]:
    if settings.tokenizer_model == settings.vector_model:
        return True, "OK (match)"
    return False, (
        f"FAIL: tokenizer={settings.tokenizer_model!r} != "
        f"embedding={settings.vector_model!r}"
    )


def sqlite_opens(settings: Settings) -> tuple[bool, str]:
    path = settings.store_path
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


def vector_extension(settings: Settings) -> tuple[bool, str]:
    try:
        ext = importlib.resources.files("sqlite_vector.binaries") / "vector"
    except (ModuleNotFoundError, FileNotFoundError) as exc:
        return False, f"FAIL: sqlite_vector binaries not found: {exc}"
    try:
        conn = sqlite3.connect(str(settings.store_path))
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


def tokenizer_load(settings: Settings) -> tuple[bool, str]:
    try:
        from docendo.retrieval import chunker

        start = time.perf_counter()
        ids = chunker.encode("hello world", settings=settings)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if not ids:
            return False, "FAIL: tokenizer returned empty ids"
        return True, (
            f"OK (model={settings.tokenizer_model!r}, "
            f"tokens={len(ids)}, elapsed_ms={elapsed_ms:.1f})"
        )
    except Exception as exc:
        return False, f"FAIL: {exc}"


async def embeddings_check(settings: Settings) -> tuple[bool, str]:
    if not settings.vector_key or not settings.vector_base:
        return False, "FAIL: VECTOR_KEY/VECTOR_BASE not set"
    try:
        from docendo.retrieval.embedder import aembed

        start = time.perf_counter()
        vecs = await aembed(["ping"], settings=settings)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if not vecs or not vecs[0]:
            return False, "FAIL: embedding returned empty vector"
        return True, f"OK (dim={len(vecs[0])}, elapsed_ms={elapsed_ms:.0f})"
    except Exception as exc:
        return False, f"FAIL: {exc}"


async def async_checks(do_embedding: bool, settings: Settings) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    if do_embedding:
        ok, msg = await embeddings_check(settings)
        out.append(("embeddings", ok, msg))
    return out


def run(
    *,
    do_embedding: bool = True,
    do_tokenizer: bool = True,
    settings: Settings | None = None,
    stream: Any = None,
) -> int:
    """Run all diagnostic checks; print results; return shell exit code."""
    import sys

    settings = settings or get_settings()
    out = stream or sys.stdout
    results: list[tuple[str, bool, str]] = []

    check_results: list[tuple[bool, str]] = [
        paths(settings),
        chat_creds(settings),
        tokenizer_match(settings),
        sqlite_opens(settings),
        vector_extension(settings),
    ]
    names = ("paths", "chat_creds", "tokenizer_match", "sqlite_opens", "vector_extension")
    for name, (ok, msg) in zip(names, check_results, strict=False):
        results.append((name, ok, msg))
    if do_tokenizer:
        ok, msg = tokenizer_load(settings)
        results.append(("tokenizer_load", ok, msg))
    results.extend(asyncio.run(async_checks(do_embedding, settings)))

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


__all__ = ["run"]
