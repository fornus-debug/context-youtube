/**
 * Transcript Cleaner — main pipeline.
 *
 * Processing order (each stage feeds into the next):
 *
 *   RawSegment[]
 *     │
 *     ▼ Stage 1: Normalize
 *     │  NFKC, bracket noise, control chars, repeated punct
 *     │
 *     ▼ Stage 2: Language detection
 *     │  Per-segment: CJK ratio → 'ja' | 'en'
 *     │
 *     ▼ Stage 3: Broken-line repair
 *     │  Orphan hyphens, orphan particles
 *     │
 *     ▼ Stage 4: Merge
 *     │  Time-gap + sentence-boundary aware fusion of fragments
 *     │
 *     ▼ Stage 5: Filler removal
 *     │  JP hesitations + EN fillers, post-merge for full context
 *     │
 *     ▼ Stage 6: Re-normalize
 *     │  Clean up whitespace artifacts left by filler removal
 *     │
 *     ▼ Stage 7: Noise scoring + filter
 *     │  Multi-factor score; discard above threshold
 *     │
 *     ▼ Stage 8: Semantic deduplication
 *     │  Jaccard 3-gram shingling with sliding window
 *     │
 *     ▼ Stage 9: Minimum-length filter
 *     │  Drop segments shorter than minChars after all processing
 *     │
 *     CleanedSegment[]
 */

import type {
  RawSegment,
  CleanedSegment,
  CleanerConfig,
  CleanerStats,
  WorkSegment,
} from "./types.js";
import { DEFAULT_CONFIG } from "./types.js";
import { normalize, detectLang, isUnrecoverable, repairBrokenLine } from "./normalizer.js";
import { removeJaFillers, removeEnFillers } from "./fillers.js";
import { mergeSegments } from "./merger.js";
import { deduplicateSegments } from "./dedup.js";
import { scoreNoise } from "./noise.js";

// ── Stage helpers ─────────────────────────────────────────────────────────────

function toWorkSegment(raw: RawSegment, lang: "ja" | "en"): WorkSegment {
  return {
    text: raw.text,
    start: raw.start,
    end: raw.start + raw.duration,
    duration: raw.duration,
    lang,
    originalCount: 1,
    noiseScore: 0,
  };
}

function applyFillers(text: string, lang: "ja" | "en"): string {
  return lang === "ja" ? removeJaFillers(text) : removeEnFillers(text);
}

function reNormalize(text: string): string {
  // Collapse multi-space artifacts left by filler removal
  return text.replace(/\s{2,}/g, " ").replace(/^[\s、。,.\-]+/, "").trim();
}

// ── Public API ────────────────────────────────────────────────────────────────

export interface CleanResult {
  segments: CleanedSegment[];
  stats: CleanerStats;
}

export function clean(
  rawSegments: RawSegment[],
  config: Partial<CleanerConfig> = {}
): CleanResult {
  const cfg: CleanerConfig = { ...DEFAULT_CONFIG, ...config };
  const inputCount = rawSegments.length;

  // ── Stage 1 + 2: Normalize + language detection ───────────────────────────
  let work: WorkSegment[] = [];
  for (const raw of rawSegments) {
    const text = normalize(raw.text);
    if (isUnrecoverable(text)) continue;
    const lang = cfg.language === "auto" ? detectLang(text) : cfg.language;
    work.push(toWorkSegment({ ...raw, text }, lang));
  }

  // ── Stage 3: Broken-line repair ───────────────────────────────────────────
  work = work.map((seg) => ({
    ...seg,
    text: repairBrokenLine(seg.text),
  }));

  // ── Stage 4: Merge fragments ──────────────────────────────────────────────
  const beforeMerge = work.length;
  work = mergeSegments(work, cfg.mergeGapSec);
  const mergedCount = beforeMerge - work.length;

  // ── Stage 5: Filler removal ───────────────────────────────────────────────
  work = work.map((seg) => ({
    ...seg,
    text: applyFillers(seg.text, seg.lang),
  }));

  // ── Stage 6: Re-normalize after filler removal ────────────────────────────
  work = work
    .map((seg) => ({ ...seg, text: reNormalize(seg.text) }))
    .filter((seg) => !isUnrecoverable(seg.text));

  // ── Stage 7: Noise scoring + filter ──────────────────────────────────────
  let removedNoise = 0;
  work = work
    .map((seg) => ({ ...seg, noiseScore: scoreNoise(seg.text, seg.lang) }))
    .filter((seg) => {
      if (seg.noiseScore > cfg.maxNoiseScore) {
        removedNoise++;
        return false;
      }
      return true;
    });

  // ── Stage 8: Semantic deduplication ──────────────────────────────────────
  const { segments: deduped, removedCount: removedDuplicates } =
    deduplicateSegments(work, cfg.dedupThreshold);

  // ── Stage 9: Minimum-length filter ───────────────────────────────────────
  const final = deduped.filter((seg) => seg.text.length >= cfg.minChars);

  const output: CleanedSegment[] = final.map((seg) => ({
    text: seg.text,
    start: seg.start,
    end: seg.end,
    noiseScore: seg.noiseScore,
    originalCount: seg.originalCount,
  }));

  const stats: CleanerStats = {
    inputSegments: inputCount,
    outputSegments: output.length,
    removedNoise,
    removedDuplicates,
    mergedCount,
    compressionRatio:
      inputCount > 0 ? output.length / inputCount : 0,
  };

  return { segments: output, stats };
}
