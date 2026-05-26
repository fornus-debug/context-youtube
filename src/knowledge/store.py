"""
Knowledge object storage.

Two-layer architecture:
  SQLite  — structured fields (type, entities, confidence, timestamp)
            enables type-filtered queries without touching embeddings
  ChromaDB — semantic embeddings of "type: content" strings
             enables similarity search across all knowledge

The embedding string is "{type}: {content}" so that semantically
similar knowledge objects of the same type cluster together.
"""

import json
import os
import sqlite3
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from .schema import KnowledgeObject, KnowledgeType

_DB_PATH = Path(os.getenv("KNOWLEDGE_DB", ".knowledge_db"))
_CHROMA_PATH = os.getenv("CHROMA_PATH", ".chroma_db")

_ef = None
_chroma = None


def _get_ef():
    global _ef
    if _ef is None:
        _ef = DefaultEmbeddingFunction()
    return _ef


def _get_chroma() -> chromadb.ClientAPI:
    global _chroma
    if _chroma is None:
        _chroma = chromadb.PersistentClient(
            path=_CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH / "knowledge.db")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_objects (
            id          TEXT PRIMARY KEY,
            video_id    TEXT NOT NULL,
            type        TEXT NOT NULL,
            content     TEXT NOT NULL,
            entities    TEXT NOT NULL,  -- JSON array
            confidence  REAL NOT NULL,
            timestamp   REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_video ON knowledge_objects(video_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_type  ON knowledge_objects(type)")
    conn.commit()
    return conn


def _chroma_collection(video_id: str) -> chromadb.Collection:
    name = f"ko_{video_id.replace('-', '_')}"
    return _get_chroma().get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


# ── Write ────────────────────────────────────────────────────────────────────

def save(objects: list[KnowledgeObject]) -> None:
    """Persist knowledge objects to SQLite + ChromaDB. Idempotent."""
    if not objects:
        return

    conn = _get_conn()
    ef = _get_ef()

    # SQLite upsert
    conn.executemany(
        """INSERT OR REPLACE INTO knowledge_objects
           (id, video_id, type, content, entities, confidence, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                obj.id, obj.video_id, obj.type, obj.content,
                json.dumps(obj.entities, ensure_ascii=False),
                obj.confidence, obj.timestamp,
            )
            for obj in objects
        ],
    )
    conn.commit()

    # ChromaDB upsert — embed "type: content" for type-aware semantic search
    video_id = objects[0].video_id
    col = _chroma_collection(video_id)
    texts = [f"{obj.type}: {obj.content}" for obj in objects]
    vectors = ef(texts)
    col.upsert(
        ids=[obj.id for obj in objects],
        embeddings=vectors,
        documents=texts,
        metadatas=[
            {
                "type": obj.type,
                "confidence": obj.confidence,
                "timestamp": obj.timestamp,
                "video_id": obj.video_id,
            }
            for obj in objects
        ],
    )


# ── Read ─────────────────────────────────────────────────────────────────────

def load_all(video_id: str) -> list[KnowledgeObject]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM knowledge_objects WHERE video_id = ?", (video_id,)
    ).fetchall()
    return [_row_to_obj(r) for r in rows]


def load_by_type(video_id: str, ktype: KnowledgeType) -> list[KnowledgeObject]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM knowledge_objects WHERE video_id = ? AND type = ?",
        (video_id, ktype),
    ).fetchall()
    return [_row_to_obj(r) for r in rows]


def semantic_search(
    video_id: str,
    query: str,
    top_k: int = 30,
    type_filter: list[KnowledgeType] | None = None,
) -> list[tuple[KnowledgeObject, float]]:
    """
    Returns (object, similarity_score) pairs, descending.
    Optionally filtered to specific knowledge types.
    """
    ef = _get_ef()
    col = _chroma_collection(video_id)
    if col.count() == 0:
        return []

    where = None
    if type_filter:
        where = {"type": {"$in": list(type_filter)}}

    query_vec = ef([query])
    results = col.query(
        query_embeddings=query_vec,
        n_results=min(top_k, col.count()),
        include=["metadatas", "distances"],
        where=where,
    )

    conn = _get_conn()
    hits = []
    for obj_id, dist in zip(
        results["ids"][0], results["distances"][0]
    ):
        row = conn.execute(
            "SELECT * FROM knowledge_objects WHERE id = ?", (obj_id,)
        ).fetchone()
        if row:
            hits.append((_row_to_obj(row), 1.0 - dist))
    return hits


def semantic_search_multi(
    video_ids: list[str],
    query: str,
    top_k: int = 20,
) -> list[tuple[KnowledgeObject, float]]:
    """
    Search across multiple videos' ChromaDB collections and merge results.

    Searches each video's collection independently (because ChromaDB collections
    are per-video), merges the (object, score) tuples, and returns the top_k
    overall by similarity score descending.

    Args:
        video_ids: List of video IDs whose collections to search.
        query:     Natural-language query string.
        top_k:     Maximum number of results to return after merging.

    Returns:
        List of (KnowledgeObject, similarity_score) tuples, descending by score.
    """
    ef = _get_ef()
    query_vec = ef([query])

    conn = _get_conn()
    all_hits: list[tuple[KnowledgeObject, float]] = []

    for video_id in video_ids:
        col = _chroma_collection(video_id)
        if col.count() == 0:
            continue

        n = min(top_k, col.count())
        results = col.query(
            query_embeddings=query_vec,
            n_results=n,
            include=["metadatas", "distances"],
        )

        for obj_id, dist in zip(results["ids"][0], results["distances"][0]):
            row = conn.execute(
                "SELECT * FROM knowledge_objects WHERE id = ?", (obj_id,)
            ).fetchone()
            if row:
                all_hits.append((_row_to_obj(row), 1.0 - dist))

    # Merge and keep top_k by similarity
    all_hits.sort(key=lambda x: x[1], reverse=True)
    return all_hits[:top_k]


def video_indexed(video_id: str) -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT 1 FROM knowledge_objects WHERE video_id = ? LIMIT 1",
        (video_id,),
    ).fetchone()
    return row is not None


def _row_to_obj(row: sqlite3.Row) -> KnowledgeObject:
    return KnowledgeObject(
        id=row["id"],
        type=row["type"],
        content=row["content"],
        entities=json.loads(row["entities"]),
        confidence=row["confidence"],
        video_id=row["video_id"],
        timestamp=row["timestamp"],
    )
