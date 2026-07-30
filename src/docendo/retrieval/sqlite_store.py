"""SQLite + FTS5 + sqlite-vector (sqliteai-vector) retrieval backend.

One :class:`SQLiteStore` instance is created per process per ``BFSI_SQLITE_PATH``.
Connections are not shared across threads; the store serializes writes with a
process-wide lock. WAL allows concurrent readers.

Schema:
- ``chunks``: regular table with one row per chunk; embedding stored as BLOB.
- ``chunks_fts``: FTS5 virtual table mirroring ``chunks.title`` and ``chunks.text``,
  kept in sync via INSERT/UPDATE/DELETE triggers.
- ``idx_chunks_circular_id``, partial index on ``(issue_date DESC, circular_id)
  WHERE chunk_index = 0``.
- ``chunks_meta``: schema version, embedding model, dimensions, tokenizer.
"""

from __future__ import annotations

import importlib.resources
import sqlite3
import struct
import threading
from pathlib import Path
from typing import Any

from docendo.config import Settings, get_settings
from docendo.logging import get_logger
from docendo.retrieval.types import (
    CircularResponse,
    CompareResponse,
    RecentItem,
    SearchHit,
    SearchResponse,
)

logger = get_logger(__name__)


SCHEMA_VERSION = 1


def _vector_to_blob(vec: list[float]) -> bytes:
    """Pack a list of floats into a little-endian float32 BLOB."""
    return struct.pack(f"<{len(vec)}f", *vec)


def _fts_escape(query: str) -> str:
    """Wrap the user query in double quotes for FTS5; double any embedded quote.

    FTS5's unicode61 tokenizer handles the rest. AND/OR/NOT in the user
    query become literal tokens, never operators.
    """
    return '"' + query.replace('"', '""') + '"'


class SQLiteStore:
    """Per-path SQLite retrieval store."""

    _write_lock = threading.Lock()
    _path_locks: dict[str, threading.Lock] = {}  # noqa: RUF012 (process-wide registry)
    _path_locks_guard = threading.Lock()

    def __init__(self, path: str | Path, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # One lock per path, lazily created.
        with SQLiteStore._path_locks_guard:
            if str(self.path) not in SQLiteStore._path_locks:
                SQLiteStore._path_locks[str(self.path)] = threading.Lock()
        self._lock = SQLiteStore._path_locks[str(self.path)]

        # Single connection for this instance; check_same_thread=False so
        # the write lock around mutating calls keeps us safe under async.
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._setup_connection()

    def _setup_connection(self) -> None:
        c = self._conn
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-65536")
        c.execute("PRAGMA mmap_size=268435456")
        c.execute("PRAGMA temp_store=MEMORY")
        c.execute("PRAGMA busy_timeout=5000")
        # Load sqliteai-vector extension.
        ext_path = importlib.resources.files("sqlite_vector.binaries") / "vector"
        c.enable_load_extension(True)
        try:
            c.load_extension(str(ext_path))
        finally:
            c.enable_load_extension(False)

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------
    def ensure_schema(self) -> None:
        dims = self.settings.bfsi_embedding_dims
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    circular_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    issue_date TEXT,
                    topic TEXT,
                    source_url TEXT NOT NULL,
                    page_start INTEGER,
                    page_end INTEGER,
                    chunk_index INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    extraction_method TEXT NOT NULL DEFAULT 'text',
                    content_hash TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    UNIQUE(circular_id, chunk_index)
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_circular_id
                    ON chunks(circular_id);

                CREATE INDEX IF NOT EXISTS idx_chunks_first_recent
                    ON chunks(issue_date DESC, circular_id)
                    WHERE chunk_index = 0;

                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    title,
                    text,
                    content='chunks',
                    content_rowid='id',
                    tokenize='unicode61 remove_diacritics 2'
                );

                CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                    INSERT INTO chunks_fts(rowid, title, text)
                    VALUES (new.id, new.title, new.text);
                END;

                CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                    INSERT INTO chunks_fts(chunks_fts, rowid, title, text)
                    VALUES ('delete', old.id, old.title, old.text);
                END;

                CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                    INSERT INTO chunks_fts(chunks_fts, rowid, title, text)
                    VALUES ('delete', old.id, old.title, old.text);
                    INSERT INTO chunks_fts(rowid, title, text)
                    VALUES (new.id, new.title, new.text);
                END;

                CREATE TABLE IF NOT EXISTS chunks_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

            # Initialize sqlite-vector on the chunks.embedding column.
            self._conn.execute(
                "SELECT vector_init(?, ?, ?)",
                (
                    "chunks",
                    "embedding",
                    f"type=FLOAT32,dimension={dims},distance=COSINE",
                ),
            )

            self._conn.execute(
                "INSERT OR REPLACE INTO chunks_meta(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO chunks_meta(key, value) VALUES (?, ?)",
                ("embedding_model", self.settings.litellm_embedding_model),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO chunks_meta(key, value) VALUES (?, ?)",
                ("embedding_dims", str(dims)),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO chunks_meta(key, value) VALUES (?, ?)",
                ("tokenizer_model", self.settings.bfsi_tokenizer_model),
            )
            self._conn.commit()
        logger.debug("SQLite schema ensured at %s (dims=%d)", self.path, dims)

    def optimize(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA optimize(0x10002)")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def upsert_chunks(self, circular_id: str, records: list[dict[Any, Any]]) -> int:
        """Replace existing chunks for ``circular_id`` with ``records``.

        Returns the number of chunk rows inserted.
        """
        if not records:
            return 0
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM chunks WHERE circular_id = ?", (circular_id,))
            cur.executemany(
                """
                INSERT INTO chunks(
                    circular_id, title, text, issue_date, topic, source_url,
                    page_start, page_end, chunk_index, chunk_count,
                    extraction_method, content_hash, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r["circular_id"],
                        r["title"],
                        r["text"],
                        r.get("issue_date"),
                        r.get("topic"),
                        r["source_url"],
                        r.get("page_start", 1),
                        r.get("page_end", 1),
                        r["chunk_index"],
                        r["chunk_count"],
                        r.get("extraction_method", "text"),
                        r["content_hash"],
                        _vector_to_blob(r["embedding"]),
                    )
                    for r in records
                ],
            )
            self._conn.commit()
            return len(records)

    def circular_is_current(self, circular_id: str, content_hash: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT c.content_hash
                FROM chunks c
                WHERE c.circular_id = ?
                ORDER BY c.chunk_index ASC
                LIMIT 1
                """,
                (circular_id,),
            ).fetchone()
        return row is not None and row[0] == content_hash

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def hybrid_search(self, query: str, limit: int = 10) -> SearchResponse:
        if not query.strip():
            return SearchResponse(query=query, hits=[])

        fts_query = _fts_escape(query)
        lexical_rows = self._lexical_search(fts_query, limit * 4)
        vector_rows = self._vector_search(query, limit * 4)

        k0 = 60
        scores: dict[int, float] = {}
        meta: dict[int, tuple[Any, ...]] = {}
        for rank, row in enumerate(lexical_rows):
            rowid = row[0]
            meta[rowid] = row
            scores[rowid] = scores.get(rowid, 0.0) + 1.0 / (k0 + rank + 1)
        for rank, row in enumerate(vector_rows):
            rowid = row[0]
            if rowid not in meta:
                meta[rowid] = row
            scores[rowid] = scores.get(rowid, 0.0) + 1.0 / (k0 + rank + 1)

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        hits: list[SearchHit] = []
        for rowid, score in ranked:
            row = meta[rowid]
            hits.append(
                SearchHit(
                    circular_id=row[1],
                    title=row[2],
                    text=row[3][: self.settings.bfsi_max_chars_per_result],
                    chunk_index=row[7],
                    chunk_count=row[8],
                    issue_date=row[4],
                    topic=row[5],
                    source_url=row[6],
                    page_start=row[9],
                    page_end=row[10],
                    extraction_method=row[11],
                    score=score,
                )
            )
        return SearchResponse(query=query, hits=hits)

    def _lexical_search(self, fts_query: str, k: int) -> list[tuple[Any, ...]]:
        sql = """
        SELECT
            c.id, c.circular_id, c.title, c.text, c.issue_date, c.topic,
            c.source_url, c.chunk_index, c.chunk_count, c.page_start, c.page_end,
            c.extraction_method,
            bm25(chunks_fts) AS rank_score
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.rowid
        WHERE chunks_fts MATCH ?
        ORDER BY rank_score ASC
        LIMIT ?
        """
        with self._lock:
            rows = self._conn.execute(sql, (fts_query, k)).fetchall()
        return rows

    def _vector_search(self, query: str, k: int) -> list[tuple[Any, ...]]:
        import asyncio

        from docendo.retrieval.embeddings import async_embed_texts

        async def _go() -> list[list[float]]:
            return await async_embed_texts([query], settings=self.settings)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Caller is already in an event loop (e.g. eval); schedule the
                # coroutine on a worker thread via to_thread.
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(asyncio.run, _go())
                    vecs = future.result()
            else:
                vecs = asyncio.run(_go())
        except RuntimeError:
            vecs = asyncio.run(_go())

        if not vecs or not vecs[0]:
            return []
        blob = _vector_to_blob(vecs[0])

        sql = """
        SELECT
            c.id, c.circular_id, c.title, c.text, c.issue_date, c.topic,
            c.source_url, c.chunk_index, c.chunk_count, c.page_start, c.page_end,
            c.extraction_method,
            v.distance
        FROM vector_full_scan('chunks', 'embedding', ?, ?) v
        JOIN chunks c ON c.id = v.rowid
        ORDER BY v.distance ASC
        LIMIT ?
        """
        with self._lock:
            rows = self._conn.execute(sql, (blob, k, k)).fetchall()
        return rows

    def get_circular(self, circular_id: str) -> CircularResponse | None:
        with self._lock:
            meta_row = self._conn.execute(
                """
                SELECT circular_id, title, issue_date, topic, source_url
                FROM chunks
                WHERE circular_id = ?
                ORDER BY chunk_index ASC
                LIMIT 1
                """,
                (circular_id,),
            ).fetchone()
            if meta_row is None:
                return None
            rows = self._conn.execute(
                """
                SELECT id, circular_id, title, text, issue_date, topic,
                       source_url, chunk_index, chunk_count, page_start, page_end,
                       extraction_method
                FROM chunks
                WHERE circular_id = ?
                ORDER BY chunk_index ASC
                """,
                (circular_id,),
            ).fetchall()
        chunks = [
            SearchHit(
                circular_id=r[1],
                title=r[2],
                text=r[3][: self.settings.bfsi_max_chars_per_result],
                chunk_index=r[7],
                chunk_count=r[8],
                issue_date=r[4],
                topic=r[5],
                source_url=r[6],
                page_start=r[9],
                page_end=r[10],
                extraction_method=r[11],
            )
            for r in rows
        ]
        return CircularResponse(
            circular_id=meta_row[0],
            title=meta_row[1],
            issue_date=meta_row[2],
            topic=meta_row[3],
            source_url=meta_row[4],
            chunks=chunks,
        )

    def list_recent(self, since: str, limit: int = 20) -> list[RecentItem]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT circular_id, title, issue_date, topic, source_url
                FROM chunks
                WHERE chunk_index = 0 AND issue_date IS NOT NULL
                  AND issue_date >= ?
                ORDER BY issue_date DESC
                LIMIT ?
                """,
                (since, limit),
            ).fetchall()
        return [
            RecentItem(
                circular_id=r[0],
                title=r[1],
                issue_date=r[2],
                topic=r[3],
                source_url=r[4],
            )
            for r in rows
        ]

    def compare(self, id_a: str, id_b: str) -> CompareResponse | None:
        a = self.get_circular(id_a)
        b = self.get_circular(id_b)
        if a is None or b is None:
            return None
        return CompareResponse(a=a, b=b)


__all__ = ["SCHEMA_VERSION", "SQLiteStore"]
