"""
YouTube search using YouTube Data API v3 (primary) with yt-dlp fallback.

Set YOUTUBE_API_KEY env var to use the official API (recommended for
cloud deployments where yt-dlp may be rate-limited by YouTube).
"""

import os
import re
from typing import Any


_MAX_DURATION = 3600


def _parse_iso8601_duration(s: str) -> int:
    """PT1H2M3S → seconds."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    h, mn, sc = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + sc


def _search_with_api(query: str, max_results: int, api_key: str) -> list[dict[str, Any]]:
    import urllib.request
    import urllib.parse
    import urllib.error
    import json

    # Step 1: search
    params = urllib.parse.urlencode({
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"YouTube API error {e.code}: {e.reason}") from e

    items = data.get("items") or []
    video_ids = []
    titles = {}
    for item in items:
        vid = (item.get("id") or {}).get("videoId")
        title = (item.get("snippet") or {}).get("title", "")
        if vid and len(vid) == 11:
            video_ids.append(vid)
            titles[vid] = title

    if not video_ids:
        return []

    # Step 2: fetch durations
    params2 = urllib.parse.urlencode({
        "part": "contentDetails",
        "id": ",".join(video_ids),
        "key": api_key,
    })
    url2 = f"https://www.googleapis.com/youtube/v3/videos?{params2}"
    try:
        with urllib.request.urlopen(url2, timeout=15) as r:
            data2 = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"YouTube API error {e.code}: {e.reason}") from e

    results = []
    for item in data2.get("items", []):
        vid = item["id"]
        duration = _parse_iso8601_duration(item["contentDetails"]["duration"])
        if duration > _MAX_DURATION:
            continue
        results.append({"id": vid, "title": titles.get(vid, ""), "duration": duration})
    return results


def _search_with_ytdlp(query: str, max_results: int) -> list[dict[str, Any]]:
    from yt_dlp import YoutubeDL

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "socket_timeout": 20,
        "retries": 2,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)

    results = []
    for entry in (info or {}).get("entries") or []:
        if not entry:
            continue
        vid = entry.get("id", "")
        if not vid or len(vid) != 11:
            continue
        try:
            duration = int(float(entry.get("duration") or 0))
        except (ValueError, TypeError):
            continue
        if duration > _MAX_DURATION:
            continue
        results.append({"id": vid, "title": entry.get("title") or "", "duration": duration})
    return results


def search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if api_key:
        return _search_with_api(query, max_results, api_key)
    return _search_with_ytdlp(query, max_results)
