"""
YouTube transcript fetching and preprocessing.
Segments raw transcript into chunks with deduplication and noise removal.
"""

import re
from dataclasses import dataclass
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound


@dataclass
class Segment:
    text: str
    start: float
    duration: float
    index: int

    @property
    def end(self) -> float:
        return self.start + self.duration

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "start": self.start,
            "duration": self.duration,
            "end": self.end,
            "index": self.index,
        }


_NOISE_PATTERNS = [
    re.compile(r"\[.*?\]"),          # [Music] [Applause] etc.
    re.compile(r"\(.*?\)"),          # (inaudible) etc.
    re.compile(r"♪.*?♪"),            # music notes
    re.compile(r"&amp;|&lt;|&gt;"),  # HTML entities
    re.compile(r"<[^>]+>"),          # leftover HTML tags
    re.compile(r"\s{2,}"),           # multiple spaces -> single
]

_FILLER_RE = re.compile(
    r"\b(um|uh|like|you know|i mean|kind of|sort of|basically|literally|actually)\b",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    for pat in _NOISE_PATTERNS:
        text = pat.sub(" ", text)
    text = _FILLER_RE.sub("", text)
    return text.strip()


def _is_duplicate(a: str, b: str, threshold: float = 0.85) -> bool:
    """Simple character-level Jaccard similarity to catch repeated captions."""
    if not a or not b:
        return False
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a or not set_b:
        return False
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return (intersection / union) >= threshold


def fetch_transcript(
    video_id: str,
    languages: tuple[str, ...] = ("ja", "en"),
) -> list[Segment]:
    """
    Fetch and preprocess YouTube transcript.
    Returns cleaned, deduplicated segments.
    """
    try:
        raw = YouTubeTranscriptApi.get_transcript(video_id, languages=list(languages))
    except TranscriptsDisabled as e:
        raise ValueError(f"Transcript unavailable for {video_id}: {e}") from e
    except NoTranscriptFound:
        # Preferred languages not found — fall back to any available transcript
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = next(iter(transcript_list))
            raw = transcript.fetch()
        except Exception as e:
            raise ValueError(f"Transcript unavailable for {video_id}: {e}") from e

    segments: list[Segment] = []
    prev_text = ""
    for i, entry in enumerate(raw):
        text = _clean(entry["text"])
        if not text or _is_duplicate(text, prev_text):
            continue
        segments.append(
            Segment(
                text=text,
                start=entry["start"],
                duration=entry.get("duration", 0.0),
                index=len(segments),
            )
        )
        prev_text = text

    return segments


def merge_into_chunks(
    segments: list[Segment],
    chunk_tokens: int = 120,
    overlap_segments: int = 1,
) -> list[dict]:
    """
    Merge fine-grained segments into larger chunks for embedding.
    Approximate token count by word count * 1.3.
    """
    chunks: list[dict] = []
    buf: list[Segment] = []
    buf_words = 0

    def flush(buf: list[Segment]) -> dict:
        text = " ".join(s.text for s in buf)
        return {
            "text": text,
            "start": buf[0].start,
            "end": buf[-1].end,
            "segment_indices": [s.index for s in buf],
        }

    for seg in segments:
        words = len(seg.text.split())
        if buf_words + words > chunk_tokens and buf:
            chunks.append(flush(buf))
            buf = buf[-overlap_segments:] if overlap_segments else []
            buf_words = sum(len(s.text.split()) for s in buf)
        buf.append(seg)
        buf_words += words

    if buf:
        chunks.append(flush(buf))

    for i, chunk in enumerate(chunks):
        chunk["chunk_id"] = i

    return chunks
