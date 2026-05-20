"""
YouTube search using yt-dlp subprocess.

Returns lightweight video metadata without downloading any media.
yt-dlp is used in pure metadata mode: no video/audio download occurs.
"""

import shutil
import subprocess
from typing import Any


_MAX_DURATION = 3600  # seconds — skip videos longer than 1 hour


def search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """
    Search YouTube and return a list of video metadata dicts.

    Args:
        query:       Search query string.
        max_results: Maximum number of results to request from YouTube.

    Returns:
        List of dicts: {"id": str, "title": str, "duration": int}
        Videos longer than 3600 s are filtered out.
        Result count may be less than max_results after filtering.

    Raises:
        ImportError:  yt-dlp is not installed / not on PATH.
        RuntimeError: yt-dlp subprocess failed for another reason.
    """
    if shutil.which("yt-dlp") is None:
        raise ImportError(
            "yt-dlp is not installed or not on PATH. "
            "Install it with:  pip install yt-dlp  or  brew install yt-dlp"
        )

    url = f"ytsearch{max_results}:{query}"
    cmd = [
        "yt-dlp",
        url,
        "--print", "%(id)s\t%(title)s\t%(duration)s",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "--skip-download",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("yt-dlp timed out after 60 s") from exc
    except OSError as exc:
        raise RuntimeError(f"Failed to launch yt-dlp: {exc}") from exc

    if proc.returncode not in (0, 1):
        # returncode 1 can be a partial failure (some videos unavailable), allow it
        stderr = proc.stderr.strip()
        raise RuntimeError(
            f"yt-dlp exited with code {proc.returncode}. stderr: {stderr}"
        )

    results: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        video_id = parts[0].strip()
        title = parts[1].strip()
        duration_raw = parts[2].strip()

        if not video_id or len(video_id) != 11:
            continue

        try:
            duration = int(float(duration_raw))
        except (ValueError, TypeError):
            # Duration unknown — skip
            continue

        if duration > _MAX_DURATION:
            continue

        results.append({"id": video_id, "title": title, "duration": duration})

    return results
