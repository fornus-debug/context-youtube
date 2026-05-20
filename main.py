#!/usr/bin/env python3
"""
Knowledge Compiler CLI.

Usage:
    python main.py <video_url_or_id> "<query>" [options]

Options:
    --title TEXT      Video title (optional, improves context)
    --refresh         Force re-extraction even if already indexed
    --inspect         Show knowledge base contents without answering
    -v, --verbose     Show pipeline stage logs
    --json            Output raw JSON result
"""

import argparse
import json
import sys

from src.pipeline import run
from src.knowledge.store import load_all, video_indexed
from src.knowledge.schema import ALL_TYPES
import re


def _extract_video_id(s: str) -> str:
    for pat in [r"(?:v=|youtu\.be/)([A-Za-z0-9_\-]{11})", r"^([A-Za-z0-9_\-]{11})$"]:
        m = re.search(pat, s)
        if m:
            return m.group(1)
    return s


def cmd_inspect(video_id: str) -> None:
    """Show the knowledge base for a video."""
    vid = _extract_video_id(video_id)
    if not video_indexed(vid):
        print(f"No knowledge base found for {vid}.")
        print("Run a query first to trigger extraction.")
        return

    objects = load_all(vid)
    print(f"\nKnowledge Base: {vid}  ({len(objects)} objects)\n")
    for ktype in ALL_TYPES:
        typed = [o for o in objects if o.type == ktype]
        if not typed:
            continue
        print(f"── {ktype.upper()} ({len(typed)}) ──")
        for obj in sorted(typed, key=lambda o: o.timestamp):
            conf = f"{obj.confidence:.0%}"
            print(f"  [{int(obj.timestamp)}s] ({conf}) {obj.content}")
            if obj.entities:
                print(f"         entities: {', '.join(obj.entities)}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Knowledge Compiler: YouTube → structured AI knowledge"
    )
    parser.add_argument("video", help="YouTube URL or video ID")
    parser.add_argument("query", nargs="?", default="", help="Question to answer")
    parser.add_argument("--title", default="")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--inspect", action="store_true",
                        help="Show extracted knowledge base")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.inspect:
        cmd_inspect(args.video)
        return

    if not args.query:
        parser.error("query is required unless --inspect is used")

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
        return

    print("\n" + "=" * 60)
    print(result["answer"])
    print("=" * 60)
    cached_label = " (cached)" if result.get("cached") else ""
    types = ", ".join(result.get("types_in_brief", []))
    print(
        f"\n[{result['knowledge_objects_used']} objects | "
        f"types: {types} | "
        f"{result['context_tokens']} tokens | "
        f"¥{result['cost']['total_jpy']:.2f}{cached_label}]"
    )


if __name__ == "__main__":
    main()
