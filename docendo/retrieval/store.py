"""SQLite + FTS5 + sqlite-vector (sqliteai-vector) retrieval backend.

One :class:`Store` instance is created per process per ``Settings.store_path``.
Connections are not shared across threads; the store serializes writes with a
per-instance lock. WAL allows concurrent readers.

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

from pydantic import HttpUrl

from docendo.config import Settings, get_settings
from docendo.exceptions import StorageError
from docendo.logging import get_logger
from docendo.retrieval.record import ChunkRecord
from docendo.retrieval.types import (
    Document,
    Hit,
    Listing,
    PairResult,
    Results,
)

logger = get_logger(__name__)


SCHEMA_VERSION = 1


def parse_blob(vec: list[float]) -> bytes:
    """Pack a list of floats into a little-endian float32 BLOB.

    Raises ``StorageError`` on empty input rather than silently returning
    an empty BLOB (which crashes sqlite-vector downstream).
    """
    if not vec:
        raise StorageError("Cannot pack an empty vector into a BLOB")
    return struct.pack(f"<{len(vec)}f", *vec)


def fts_escape(query: str) -> str:
    """Wrap the user query in double quotes for FTS5; double any embedded quote.

    FTS5's unicode61 tokenizer handles the rest. AND/OR/NOT in the user
    query become literal tokens, never operators.
    """
    return '"' + query.replace('"', '""') + '"'


def from_row(row: sqlite3.Row, chunk_max_chars: int) -> Hit:
    """Build a Hit from a sqlite3.Row (named access).

    ``chunk_max_chars`` is passed in by the owning :class:`Store` rather
    than read from the global :func:`get_settings` cache, so row
    decoding stays pure with respect to its inputs and is safe to call
    from any thread.
    """
    return Hit(
        circular_id=row["circular_id"],
        title=row["title"],
        text=row["text"][:chunk_max_chars],
        chunk_index=row["chunk_index"],
        chunk_count=row["chunk_count"],
        issue_date=row["issue_date"],
        topic=row["topic"],
        source_url=HttpUrl(row["source_url"]),
        page_estimate_start=row["page_estimate_start"],
        page_estimate_end=row["page_estimate_end"],
        extraction_method=row["extraction_method"],
    )


class Store:
    """Per-path SQLite retrieval store."""

    def __init__(self, path: str | Path, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.chunk_max_chars = self.settings.chunk_max_chars

        # Per-instance lock; writes are serialized.
        self._lock = threading.Lock()

        # Single connection for this instance; check_same_thread=False so
        # the write lock around mutating calls keeps us safe under async.
        self._conn = sqlite3.connect(
            str(self.path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._conn.row_factory = sqlite3.Row
        self.setup_connection()

    def setup_connection(self) -> None:
        c = self._conn
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-65536")
        c.execute("PRAGMA mmap_size=268435456")
        c.execute("PRAGMA temp_store=MEMORY")
        c.execute("PRAGMA busy_timeout=5000")
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
        dims = self.settings.vector_dims
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
                    page_estimate_start INTEGER,
                    page_estimate_end INTEGER,
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
                ("embedding_model", self.settings.vector_id),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO chunks_meta(key, value) VALUES (?, ?)",
                ("embedding_dims", str(dims)),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO chunks_meta(key, value) VALUES (?, ?)",
                ("tokenizer_model", self.settings.tokenizer_model),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO chunks_meta(key, value) VALUES (?, ?)",
                ("rrf_k", str(self.settings.rrf_k)),
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
    def upsert_chunks(self, circular_id: str, records: list[ChunkRecord]) -> int:
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
                    page_estimate_start, page_estimate_end, chunk_index, chunk_count,
                    extraction_method, content_hash, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r.circular_id,
                        r.title,
                        r.text,
                        r.issue_date,
                        r.topic,
                        str(r.source_url),
                        r.page_estimate_start,
                        r.page_estimate_end,
                        r.chunk_index,
                        r.chunk_count,
                        r.extraction_method,
                        r.content_hash,
                        parse_blob(r.embedding),
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
                SELECT content_hash FROM chunks
                WHERE circular_id = ?
                ORDER BY chunk_index ASC
                LIMIT 1
                """,
                (circular_id,),
            ).fetchone()
        return row is not None and row["content_hash"] == content_hash

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def hybrid_search(self, query: str, limit: int = 10) -> Results:
        if not query.strip():
            return Results(query=query, hits=[])


        fts_query = fts_escape(query)
        lexical_rows = self.lex(fts_query, limit * 4)
        vector_rows = self.vec(query, limit * 4)

        k0 = self.settings.rrf_k
        scores: dict[int, float] = {}
        meta: dict[int, sqlite3.Row] = {}
        for rank, row in enumerate(lexical_rows):
            rowid = row["id"]
            meta[rowid] = row
            scores[rowid] = scores.get(rowid, 0.0) + 1.0 / (k0 + rank + 1)
        for rank, row in enumerate(vector_rows):
            rowid = row["id"]
            if rowid not in meta:
                meta[rowid] = row
            scores[rowid] = scores.get(rowid, 0.0) + 1.0 / (k0 + rank + 1)

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        hits: list[Hit] = []
        for rowid, score in ranked:
            row = meta[rowid]
            hit = from_row(row, self.chunk_max_chars)
            hit = hit.model_copy(update={"score": score})
            hits.append(hit)
        return Results(query=query, hits=hits)

    def lex(self, fts_query: str, k: int) -> list[sqlite3.Row]:
        sql = """
        SELECT c.id, c.circular_id, c.title, c.text, c.issue_date, c.topic,
               c.source_url, c.chunk_index, c.chunk_count,
               c.page_estimate_start, c.page_estimate_end, c.extraction_method,
               bm25(chunks_fts) AS rank_score
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.rowid
        WHERE chunks_fts MATCH ?
        ORDER BY rank_score ASC
        LIMIT ?
        """
        with self._lock:
            return list(self._conn.execute(sql, (fts_query, k)).fetchall())

    def vec(self, query: str, k: int) -> list[sqlite3.Row]:
        import asyncio

        from docendo.retrieval.embedder import aembed

        async def go() -> list[list[float]]:
            return await aembed([query], settings=self.settings)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(asyncio.run, go())
                    vecs = future.result()
            else:
                vecs = asyncio.run(go())
        except RuntimeError:
            vecs = asyncio.run(go())

        if not vecs or not vecs[0]:
            return []
        blob = parse_blob(vecs[0])

        sql = """
        SELECT c.id, c.circular_id, c.title, c.text, c.issue_date, c.topic,
               c.source_url, c.chunk_index, c.chunk_count,
               c.page_estimate_start, c.page_estimate_end, c.extraction_method,
               v.distance
        FROM vector_full_scan('chunks', 'embedding', ?, ?) v
        JOIN chunks c ON c.id = v.rowid
        ORDER BY v.distance ASC
        LIMIT ?
        """
        with self._lock:
            return list(self._conn.execute(sql, (blob, k, k)).fetchall())

    def fetch(self, circular_id: str) -> Document | None:
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
                       source_url, chunk_index, chunk_count,
                       page_estimate_start, page_estimate_end, extraction_method
                FROM chunks
                WHERE circular_id = ?
                ORDER BY chunk_index ASC
                """,
                (circular_id,),
            ).fetchall()
        chunks = [from_row(r, self.chunk_max_chars) for r in rows]
        return Document(
            circular_id=meta_row["circular_id"],
            title=meta_row["title"],
            issue_date=meta_row["issue_date"],
            topic=meta_row["topic"],
            source_url=HttpUrl(meta_row["source_url"]),
            chunks=chunks,
        )

    def list_recent(
        self,
        since: str,
        limit: int = 20,
        include_unknown_date: bool = False,
    ) -> list[Listing]:
        where = "chunk_index = 0 AND issue_date IS NOT NULL AND issue_date >= ?"
        params: tuple[Any, ...] = (since,)
        if include_unknown_date:
            where = "chunk_index = 0 AND (issue_date IS NULL OR issue_date >= ?)"
        sql = f"""
        SELECT circular_id, title, issue_date, topic, source_url
        FROM chunks
        WHERE {where}
        ORDER BY issue_date IS NULL, issue_date DESC
        LIMIT ?
        """
        params = (*params, limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [
            Listing(
                circular_id=r["circular_id"],
                title=r["title"],
                issue_date=r["issue_date"],
                topic=r["topic"],
                source_url=HttpUrl(r["source_url"]),
            )
            for r in rows
        ]

    def compare(self, id_a: str, id_b: str) -> PairResult | None:
        a = self.fetch(id_a)
        b = self.fetch(id_b)
        if a is None or b is None:
            return None
        return PairResult(a=a, b=b)


__all__ = ["SCHEMA_VERSION", "Store", "from_row", "fts_escape", "parse_blob"]
