#!/usr/bin/env python3
"""
Context OS MVP — CLI entry point.

Usage:
    python main.py <video_url_or_id> "<query>" [--title "Video Title"] [--refresh] [-v]
"""

import argparse
import json
import sys

from src.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Context OS: YouTube transcript Q&A with minimal LLM cost"
    )
    parser.add_argument("video", help="YouTube URL or video ID")
    parser.add_argument("query", help="Question to ask about the video")
    parser.add_argument("--title", default="", help="Video title (optional)")
    parser.add_argument(
        "--refresh", action="store_true", help="Force re-fetch and re-index"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    try:
        result = run(
            video_url_or_id=args.video,
            query=args.query,
            title=args.title,
            force_refresh=args.refresh,
            verbose=args.verbose,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n" + "=" * 60)
        print(result["answer"])
        print("=" * 60)
        cached_label = " (cached)" if result.get("cached") else ""
        print(
            f"\n[{result['chunks_used']} chunks | "
            f"{result['context_tokens']} tokens | "
            f"¥{result['cost']['total_jpy']:.2f}{cached_label}]"
        )


if __name__ == "__main__":
    main()
