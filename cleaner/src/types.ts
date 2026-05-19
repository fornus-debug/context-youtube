// ── Input / Output shapes ────────────────────────────────────────────────────

export interface RawSegment {
  text: string;
  start: number;    // seconds
  duration: number; // seconds
}

export interface CleanedSegment {
  text: string;
  start: number;
  end: number;
  noiseScore: number;    // 0.0 = clean, 1.0 = pure noise
  originalCount: number; // how many raw segments merged into this
}

// ── Pipeline configuration ───────────────────────────────────────────────────

export interface CleanerConfig {
  /** Discard segments shorter than this after cleaning (chars) */
  minChars: number;
  /** Discard segments with noise score above this threshold */
  maxNoiseScore: number;
  /** Merge adjacent segments if gap is within this value (seconds) */
  mergeGapSec: number;
  /** Jaccard similarity above which two segments are considered near-duplicates */
  dedupThreshold: number;
  /** Target language for filler/boundary rules. 'auto' = detect per-segment. */
  language: "ja" | "en" | "auto";
}

export const DEFAULT_CONFIG: CleanerConfig = {
  minChars: 8,
  maxNoiseScore: 0.72,
  mergeGapSec: 1.8,
  dedupThreshold: 0.72,
  language: "auto",
};

// ── Processing stats ─────────────────────────────────────────────────────────

export interface CleanerStats {
  inputSegments: number;
  outputSegments: number;
  removedNoise: number;
  removedDuplicates: number;
  mergedCount: number;
  compressionRatio: number; // outputSegments / inputSegments
}

// ── Intermediate pipeline node ───────────────────────────────────────────────

export interface WorkSegment extends RawSegment {
  end: number;
  lang: "ja" | "en";
  originalCount: number;
  noiseScore: number;
}
