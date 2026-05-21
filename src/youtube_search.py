"""
YouTube search using yt-dlp Python API (no subprocess overhead).
"""

from typing import Any


_MAX_DURATION = 3600  # skip videos longer than 1 hour


def search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise ImportError("yt-dlp is not installed. Run: pip install yt-dlp") from exc

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "socket_timeout": 20,
        "retries": 2,
    }

    url = f"ytsearch{max_results}:{query}"
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = (info or {}).get("entries") or []
    results: list[dict[str, Any]] = []
    for entry in entries:
        if not entry:
            continue
        video_id = entry.get("id", "")
        if not video_id or len(video_id) != 11:
            continue
        title = entry.get("title") or ""
        duration = entry.get("duration") or 0
        try:
            duration = int(float(duration))
        except (ValueError, TypeError):
            continue
        if duration > _MAX_DURATION:
            continue
        results.append({"id": video_id, "title": title, "duration": duration})

    return results
