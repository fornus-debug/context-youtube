"""
Local embedding generation and ChromaDB storage.
Uses sentence-transformers (free, no API cost).
"""

import os
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_DB_PATH = os.getenv("CHROMA_PATH", ".chroma_db")

_model: Optional[SentenceTransformer] = None
_client: Optional[chromadb.ClientAPI] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _collection_name(video_id: str) -> str:
    # ChromaDB collection names must be alphanumeric + underscores/hyphens
    return f"yt_{video_id.replace('-', '_')}"


def embed_and_store(video_id: str, chunks: list[dict]) -> None:
    """Embed chunks and persist to ChromaDB. Idempotent via upsert."""
    model = _get_model()
    client = _get_client()
    col = client.get_or_create_collection(
        name=_collection_name(video_id),
        metadata={"hnsw:space": "cosine"},
    )

    texts = [c["text"] for c in chunks]
    vectors = model.encode(texts, batch_size=64, show_progress_bar=False).tolist()
    ids = [f"{video_id}_{c['chunk_id']}" for c in chunks]
    metadatas = [
        {
            "start": c["start"],
            "end": c["end"],
            "chunk_id": c["chunk_id"],
            "video_id": video_id,
        }
        for c in chunks
    ]

    col.upsert(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)


def vector_search(
    video_id: str,
    query: str,
    top_k: int = 20,
) -> list[dict]:
    """Return top_k chunks by cosine similarity."""
    model = _get_model()
    client = _get_client()
    col_name = _collection_name(video_id)

    try:
        col = client.get_collection(col_name)
    except Exception:
        return []

    query_vec = model.encode([query], show_progress_bar=False).tolist()
    results = col.query(
        query_embeddings=query_vec,
        n_results=min(top_k, col.count()),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "text": doc,
            "meta": meta,
            "vector_score": 1.0 - dist,  # cosine similarity
        })
    return hits


def collection_exists(video_id: str) -> bool:
    client = _get_client()
    col_name = _collection_name(video_id)
    try:
        client.get_collection(col_name)
        return True
    except Exception:
        return False
