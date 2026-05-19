/**
 * Sentence merge logic.
 *
 * YouTube auto-captions split utterances into tiny fragments:
 *   "今日は" | "機械学習" | "について" | "話します"
 *
 * Strategy:
 *   1. Time-gap gating: if gap > mergeGapSec → hard boundary, never merge
 *   2. Sentence-boundary detection: ends with 。.!? → boundary
 *   3. Continuation signals: next line starts with particle/lowercase → merge
 *   4. Length cap: merged result must not exceed maxMergeChars
 *
 * Merge is applied before filler removal so we preserve full context
 * for accurate noise scoring.
 */

import {
  endsWithSentence,
  startsLower,
  jaStartsContinuation,
} from "./normalizer.js";
import type { WorkSegment } from "./types.js";

const MAX_MERGE_CHARS = 300;

function gapSec(a: WorkSegment, b: WorkSegment): number {
  return b.start - a.end;
}

function shouldMerge(
  current: WorkSegment,
  next: WorkSegment,
  mergeGapSec: number
): boolean {
  // Hard time-gap boundary
  if (gapSec(current, next) > mergeGapSec) return false;

  // Hard length cap
  if (current.text.length + next.text.length > MAX_MERGE_CHARS) return false;

  const lang = current.lang;

  // If current ends with a sentence terminator → do NOT merge
  if (endsWithSentence(current.text, lang)) return false;

  // Continuation signals favour merging
  if (lang === "en" && startsLower(next.text)) return true;
  if (lang === "ja" && jaStartsContinuation(next.text)) return true;

  // Short fragment heuristic: if current is very short, merge
  const currentWords =
    lang === "ja"
      ? current.text.replace(/\s/g, "").length
      : current.text.split(/\s+/).length;
  if (currentWords <= 4) return true;

  return false;
}

function joinTexts(a: string, b: string, lang: "ja" | "en"): string {
  // Japanese: no space between kanji/kana; add space only if both are ASCII
  if (lang === "ja") {
    const aEnd = a.slice(-1);
    const bStart = b[0] ?? "";
    const needsSpace = /[a-zA-Z0-9]/.test(aEnd) && /[a-zA-Z0-9]/.test(bStart);
    return needsSpace ? `${a} ${b}` : `${a}${b}`;
  }
  return `${a} ${b}`;
}

export function mergeSegments(
  segments: WorkSegment[],
  mergeGapSec: number
): WorkSegment[] {
  if (segments.length === 0) return [];

  const result: WorkSegment[] = [];
  let current = { ...segments[0] } as WorkSegment;

  for (let i = 1; i < segments.length; i++) {
    const next = segments[i] as WorkSegment;
    if (shouldMerge(current, next, mergeGapSec)) {
      current = {
        text: joinTexts(current.text, next.text, current.lang),
        start: current.start,
        end: next.end,
        duration: next.end - current.start,
        lang: current.lang,
        originalCount: current.originalCount + next.originalCount,
        noiseScore: 0, // recalculated later
      };
    } else {
      result.push(current);
      current = { ...next };
    }
  }
  result.push(current);

  return result;
}
