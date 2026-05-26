"""
FastAPI application — AI Context Generation Engine HTTP interface.

Endpoints:
  POST /api/query    — Full search pipeline (search + extract + answer)
  POST /api/extract  — Extract knowledge objects for a single video
  GET  /api/knowledge/{video_id} — Retrieve stored objects for a video
  GET  /api/health   — Health check
"""

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="AI Context Generation Engine",
    description="Knowledge Compiler pipeline: YouTube search → structured knowledge extraction → LLM answer",
    version="0.1.0",
)

_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The question to answer")
    max_videos: int = Field(5, ge=1, le=10, description="Max YouTube videos to search")
    force_refresh: bool = Field(False, description="Bypass cache and re-extract")


class VideoSearched(BaseModel):
    id: str
    title: str
    duration: int


class CostBreakdown(BaseModel):
    input_tokens: int
    output_tokens: int
    total_usd: float
    total_jpy: float


class QueryResponse(BaseModel):
    answer: str
    videos_searched: list[VideoSearched]
    types_in_brief: list[str]
    knowledge_objects_used: int
    context_tokens: int
    cost: CostBreakdown
    cached: bool


class ExtractRequest(BaseModel):
    video_id: str = Field(..., min_length=1, description="YouTube video ID (11 chars) or URL")
    force: bool = Field(False, description="Re-extract even if already indexed")


class ExtractStats(BaseModel):
    total: int
    by_type: dict[str, int]
    already_indexed: bool


class ExtractResponse(BaseModel):
    knowledge_objects: list[dict]
    stats: ExtractStats


class KnowledgeResponse(BaseModel):
    video_id: str
    objects_by_type: dict[str, list[dict]]
    total: int


class HealthResponse(BaseModel):
    status: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_video_id(url_or_id: str) -> str:
    import re
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_\-]{11})",
        r"^([A-Za-z0-9_\-]{11})$",
    ]
    for pat in patterns:
        m = re.search(pat, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url_or_id}")


def _compress_for_extraction(chunks: list[dict]) -> str:
    lines = []
    for chunk in sorted(chunks, key=lambda c: c.get("start", 0)):
        ts = int(chunk.get("start", 0))
        lines.append(f"[{ts}s] {chunk['text']}")
    return "\n".join(lines)


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Simple health check."""
    return HealthResponse(status="ok")


@app.post("/api/query", response_model=QueryResponse, tags=["pipeline"])
def query(req: QueryRequest) -> QueryResponse:
    from src.pipeline import run_search
    try:
        result = run_search(
            query=req.query,
            max_videos=req.max_videos,
            force_refresh=req.force_refresh,
            verbose=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    videos = [
        VideoSearched(id=v["id"], title=v["title"], duration=v["duration"])
        for v in result.get("videos_searched", [])
    ]
    raw_cost = result.get("cost", {})
    cost = CostBreakdown(
        input_tokens=raw_cost.get("input_tokens", 0),
        output_tokens=raw_cost.get("output_tokens", 0),
        total_usd=raw_cost.get("total_usd", 0.0),
        total_jpy=raw_cost.get("total_jpy", 0.0),
    )

    return QueryResponse(
        answer=result.get("answer", ""),
        videos_searched=videos,
        types_in_brief=result.get("types_in_brief", []),
        knowledge_objects_used=result.get("knowledge_objects_used", 0),
        context_tokens=result.get("context_tokens", 0),
        cost=cost,
        cached=result.get("cached", False),
    )


@app.post("/api/extract", response_model=ExtractResponse, tags=["knowledge"])
def extract_video(req: ExtractRequest) -> ExtractResponse:
    from src.knowledge.store import load_all, video_indexed, save
    from src.knowledge.extractor import extract
    from src.transcript import fetch_transcript, merge_into_chunks
    try:
        video_id = _extract_video_id(req.video_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    already_indexed = video_indexed(video_id)

    if already_indexed and not req.force:
        objects = load_all(video_id)
    else:
        try:
            segments = fetch_transcript(video_id)
            chunks = merge_into_chunks(segments, chunk_tokens=120, overlap_segments=1)
            compressed = _compress_for_extraction(chunks)
            objects = extract(video_id, compressed, verbose=False)
            save(objects)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    by_type: dict[str, int] = {}
    for obj in objects:
        by_type[obj.type] = by_type.get(obj.type, 0) + 1

    return ExtractResponse(
        knowledge_objects=[obj.to_dict() for obj in objects],
        stats=ExtractStats(
            total=len(objects),
            by_type=by_type,
            already_indexed=already_indexed,
        ),
    )


@app.get("/api/knowledge/{video_id}", response_model=KnowledgeResponse, tags=["knowledge"])
def get_knowledge(video_id: str) -> KnowledgeResponse:
    from src.knowledge.store import load_all, video_indexed
    try:
        vid = _extract_video_id(video_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not video_indexed(vid):
        raise HTTPException(
            status_code=404,
            detail=f"Video '{vid}' has not been indexed. POST /api/extract first.",
        )

    objects = load_all(vid)  # type: ignore[possibly-undefined]
    objects_by_type: dict[str, list[dict]] = {}
    for obj in objects:
        objects_by_type.setdefault(obj.type, []).append(obj.to_dict())

    return KnowledgeResponse(
        video_id=vid,
        objects_by_type=objects_by_type,
        total=len(objects),
    )
