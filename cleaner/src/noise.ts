/**
 * Multi-factor noise scoring.
 *
 * Score 0.0 = perfectly clean, 1.0 = pure noise.
 * Segments above CleanerConfig.maxNoiseScore are discarded.
 *
 * Factors and weights:
 *   fillerRatio      0.30  — fraction of chars that are filler words
 *   repetitionScore  0.25  — intra-segment repeated n-gram density
 *   lengthPenalty    0.20  — very short segments add no semantic value
 *   incompleteness   0.15  — no sentence-ending punct + very short
 *   unicodeNoise     0.10  — high ratio of non-alphanumeric chars
 */

import { fillerRatio } from "./fillers.js";
import { endsWithSentence } from "./normalizer.js";

const WEIGHTS = {
  filler: 0.40,       // dominant signal: fillers = zero semantic value
  repetition: 0.10,
  length: 0.25,       // very short fragments are near-useless for embedding
  incompleteness: 0.20,
  unicode: 0.05,
} as const;

// ── Individual factor computations ───────────────────────────────────────────

function repetitionScore(text: string): number {
  // Measure how much of the text is n-gram repetition (n=2,3)
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length < 4) return 0;

  let repeated = 0;
  // Bigram repetition
  const bigrams = new Map<string, number>();
  for (let i = 0; i < words.length - 1; i++) {
    const key = `${words[i]}_${words[i + 1]}`;
    bigrams.set(key, (bigrams.get(key) ?? 0) + 1);
  }
  for (const count of bigrams.values()) {
    if (count > 1) repeated += count - 1;
  }

  // Character-level trigram repetition for Japanese
  const norm = text.replace(/\s/g, "");
  if (norm.length >= 6) {
    const trigrams = new Map<string, number>();
    for (let i = 0; i <= norm.length - 3; i++) {
      const key = norm.slice(i, i + 3);
      trigrams.set(key, (trigrams.get(key) ?? 0) + 1);
    }
    for (const count of trigrams.values()) {
      if (count > 2) repeated += (count - 2) * 0.5;
    }
  }

  return Math.min(repeated / Math.max(words.length, 1), 1.0);
}

function lengthPenalty(text: string): number {
  const len = text.replace(/\s/g, "").length;
  if (len === 0) return 1.0;
  if (len < 4) return 0.95;
  if (len < 8) return 0.6;
  if (len < 12) return 0.25;
  return 0;
}

function incompletenessScore(text: string, lang: "ja" | "en"): number {
  // Reward segments that end with sentence terminators
  if (endsWithSentence(text, lang)) return 0;
  const wordCount = text.split(/\s+/).filter(Boolean).length;
  // Short and incomplete = likely noise fragment
  if (wordCount <= 3) return 0.9;
  if (wordCount <= 6) return 0.4;
  return 0.1;
}

function unicodeNoiseScore(text: string): number {
  if (!text) return 1.0;
  const alphanumeric = (text.match(/[\p{L}\p{N}]/gu) ?? []).length;
  const total = text.replace(/\s/g, "").length;
  if (total === 0) return 1.0;
  const ratio = alphanumeric / total;
  // Penalize when <50% of chars are letters/numbers
  return ratio >= 0.5 ? 0 : (0.5 - ratio) * 2;
}

// ── Public scorer ─────────────────────────────────────────────────────────────

export function scoreNoise(text: string, lang: "ja" | "en"): number {
  const f = fillerRatio(text, lang);
  const r = repetitionScore(text);
  const l = lengthPenalty(text);
  const i = incompletenessScore(text, lang);
  const u = unicodeNoiseScore(text);

  const score =
    f * WEIGHTS.filler +
    r * WEIGHTS.repetition +
    l * WEIGHTS.length +
    i * WEIGHTS.incompleteness +
    u * WEIGHTS.unicode;

  return Math.min(Math.max(score, 0), 1);
}

/** Detailed breakdown for debugging / tuning */
export function explainNoise(
  text: string,
  lang: "ja" | "en"
): Record<string, number> {
  return {
    fillerRatio: fillerRatio(text, lang),
    repetitionScore: repetitionScore(text),
    lengthPenalty: lengthPenalty(text),
    incompletenessScore: incompletenessScore(text, lang),
    unicodeNoiseScore: unicodeNoiseScore(text),
    total: scoreNoise(text, lang),
  };
}
