"""
YouTube transcript fetching and preprocessing.
Segments raw transcript into chunks with deduplication and noise removal.

Cloud IP blocking: YouTube blocks transcript requests from Render/cloud IPs.
Set WEBSHARE_PROXY_USERNAME + WEBSHARE_PROXY_PASSWORD (webshare.io free tier)
or YOUTUBE_PROXY_HTTP / YOUTUBE_PROXY_HTTPS (any HTTP proxy URL) to bypass.
"""

import os
import re
from dataclasses import dataclass

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    YouTubeRequestFailed,
)


class CloudIpBlockedError(ValueError):
    """YouTube is blocking transcript requests from this cloud IP address."""
    pass


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


_COOKIES_PATH = os.getenv("YOUTUBE_COOKIES_FILE", "/etc/secrets/youtube_cookies.txt")


def _make_api() -> YouTubeTranscriptApi:
    """Build YouTubeTranscriptApi instance.

    Priority:
    1. Cookies file (YOUTUBE_COOKIES_FILE or /etc/secrets/youtube_cookies.txt)
    2. Webshare proxy (WEBSHARE_PROXY_USERNAME + WEBSHARE_PROXY_PASSWORD)
    3. Generic proxy (YOUTUBE_PROXY_HTTP / YOUTUBE_PROXY_HTTPS)
    4. No auth (local dev only)
    """
    import http.cookiejar
    import requests

    session: requests.Session | None = None
    if os.path.exists(_COOKIES_PATH):
        jar = http.cookiejar.MozillaCookieJar(_COOKIES_PATH)
        try:
            jar.load(ignore_discard=True, ignore_expires=True)
            session = requests.Session()
            session.cookies = jar  # type: ignore[assignment]
        except Exception:
            session = None  # corrupt/empty cookies file — fall through

    ws_user = os.getenv("WEBSHARE_PROXY_USERNAME", "")
    ws_pass = os.getenv("WEBSHARE_PROXY_PASSWORD", "")
    if ws_user and ws_pass:
        from youtube_transcript_api.proxies import WebshareProxyConfig
        return YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=ws_user,
                proxy_password=ws_pass,
            ),
            http_client=session,
        )

    http_proxy = os.getenv("YOUTUBE_PROXY_HTTP", "")
    https_proxy = os.getenv("YOUTUBE_PROXY_HTTPS", "") or http_proxy
    if http_proxy or https_proxy:
        from youtube_transcript_api.proxies import GenericProxyConfig
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(
                http_url=http_proxy or None,
                https_url=https_proxy or None,
            ),
            http_client=session,
        )

    return YouTubeTranscriptApi(http_client=session)


def _fetch_timedtext_direct(video_id: str) -> list[dict] | None:
    """
    Fallback: hit YouTube's timedtext endpoint directly (bypasses video-page block).
    Returns raw segment dicts or None if unavailable.
    """
    import urllib.request
    import json as _json

    for lang in ("ja", "en", ""):
        params = f"v={video_id}&fmt=json3"
        if lang:
            params += f"&lang={lang}"
        url = f"https://www.youtube.com/api/timedtext?{params}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "Referer": f"https://www.youtube.com/watch?v={video_id}",
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                if r.status != 200:
                    continue
                data = _json.loads(r.read())
        except Exception:
            continue

        segments = []
        for event in data.get("events", []):
            segs = event.get("segs", [])
            if not segs:
                continue
            text = "".join(s.get("utf8", "") for s in segs).strip()
            if text and text.strip() != "\n":
                segments.append({
                    "text": text,
                    "start": event.get("tStartMs", 0) / 1000,
                    "duration": event.get("dDurationMs", 0) / 1000,
                })
        if segments:
            return segments

    return None


def fetch_transcript(
    video_id: str,
    languages: tuple[str, ...] = ("ja", "en"),
) -> list[Segment]:
    """
    Fetch and preprocess YouTube transcript.
    Returns cleaned, deduplicated segments.
    """
    api = _make_api()
    raw = None
    try:
        raw = api.fetch(video_id, languages=list(languages))
    except TranscriptsDisabled as e:
        raise ValueError(f"Transcript unavailable for {video_id}: {e}") from e
    except NoTranscriptFound:
        try:
            tl = api.list(video_id)
            transcript = next(iter(tl))
            raw = transcript.fetch()
        except YouTubeRequestFailed as e:
            if "403" in str(e):
                raise CloudIpBlockedError(
                    f"YouTube blocked transcript access for {video_id} (403 Forbidden). "
                    "Running on a cloud IP — set WEBSHARE_PROXY_USERNAME + "
                    "WEBSHARE_PROXY_PASSWORD (webshare.io) or YOUTUBE_PROXY_HTTP to bypass."
                ) from e
            raise ValueError(f"Transcript unavailable for {video_id}: {e}") from e
        except Exception as e:
            raise ValueError(f"Transcript unavailable for {video_id}: {e}") from e
    except YouTubeRequestFailed as e:
        if "403" in str(e):
            raise CloudIpBlockedError(
                f"YouTube blocked transcript access for {video_id} (403 Forbidden). "
                "Running on a cloud IP — set WEBSHARE_PROXY_USERNAME + "
                "WEBSHARE_PROXY_PASSWORD (webshare.io) or YOUTUBE_PROXY_HTTP to bypass."
            ) from e
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
