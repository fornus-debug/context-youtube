/**
 * Text normalization before any other processing.
 *
 * Goal: produce canonical, clean Unicode text that is maximally
 * useful for embedding — consistent characters, no visual noise.
 *
 * Pipeline order matters:
 *   1. NFKC normalization (full-width → half-width, ligatures → base)
 *   2. Bracket / HTML noise removal
 *   3. Control character removal
 *   4. Punctuation normalization
 *   5. Repeated character collapse
 *   6. Whitespace normalization
 */

import { removeBracketNoise, isSymbolOnly } from "./fillers.js";

// ── Regex constants ──────────────────────────────────────────────────────────

// Control chars except newline/tab
const CONTROL_RE = /[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g;

// Excessive repeated punctuation: !!! → !, ~~~ → ~
const REPEATED_PUNCT_RE = /([!?。！？~～…]{2,})/g;

// Repeated words/phrases in same line: "機械学習 機械学習 機械学習" → "機械学習"
const REPEATED_WORD_EN_RE = /\b(\w{3,})\s+\1(\s+\1)+\b/gi;
// Japanese: character sequence repetition (no word boundary available)
const REPEATED_PHRASE_JA_RE = /([぀-鿿]{2,8})(\1){2,}/g;

// Multiple whitespace → single space
const MULTI_SPACE_RE = /[ \t]+/g;

// Orphan hyphen at line start (broken mid-word subtitle)
const ORPHAN_HYPHEN_RE = /^[-–—]\s*/;

// ── Language detection ───────────────────────────────────────────────────────

const CJK_RE = /[぀-ゟ゠-ヿ一-鿿豈-﫿]/;

export function detectLang(text: string): "ja" | "en" {
  const cjkCount = (text.match(new RegExp(CJK_RE.source, "g")) ?? []).length;
  return cjkCount / Math.max(text.replace(/\s/g, "").length, 1) > 0.25
    ? "ja"
    : "en";
}

// ── Sentence boundary detection ──────────────────────────────────────────────

const JA_SENTENCE_END_RE = /[。！？]$/;
// Require at least one word character before the terminator to avoid
// matching symbol-only strings like "..." as complete sentences.
const EN_SENTENCE_END_RE = /\w[^.!?]*[.!?](\s|$)/;

export function endsWithSentence(text: string, lang: "ja" | "en"): boolean {
  return lang === "ja"
    ? JA_SENTENCE_END_RE.test(text.trimEnd())
    : EN_SENTENCE_END_RE.test(text.trimEnd());
}

// Starts with lowercase letter → likely mid-sentence continuation (EN only)
export function startsLower(text: string): boolean {
  const first = text.trimStart()[0];
  return first !== undefined && first === first.toLowerCase() && /[a-z]/.test(first);
}

// Japanese: starts with particle/conjunctive → continuation
const JA_CONTINUATION_START_RE = /^[はがをにでものとからまでより]/u;
export function jaStartsContinuation(text: string): boolean {
  return JA_CONTINUATION_START_RE.test(text.trimStart());
}

// ── Core normalizer ──────────────────────────────────────────────────────────

export function normalize(raw: string): string {
  let t = raw;

  // 1. Unicode NFKC: full-width numbers/letters → ASCII, ligatures → base chars
  t = t.normalize("NFKC");

  // 2. Remove bracket noise ([音楽], [Music], HTML entities)
  t = removeBracketNoise(t);

  // 3. Strip control characters
  t = t.replace(CONTROL_RE, "");

  // 4. Orphan hyphen from mid-word subtitle break
  t = t.replace(ORPHAN_HYPHEN_RE, "");

  // 5. Repeated punctuation collapse
  t = t.replace(REPEATED_PUNCT_RE, (_, p) => {
    const char = p[0] as string;
    // Keep "..." for ellipsis intent; collapse everything else
    return char === "." || char === "…" ? "…" : char;
  });

  // 6. Repeated word/phrase deduplication within line
  t = t.replace(REPEATED_WORD_EN_RE, "$1");
  t = t.replace(REPEATED_PHRASE_JA_RE, "$1");

  // 7. Whitespace normalization
  t = t.replace(MULTI_SPACE_RE, " ").trim();

  return t;
}

/**
 * Returns true if the segment is too broken to recover:
 * pure symbols, empty after normalize, or single-character.
 */
export function isUnrecoverable(text: string): boolean {
  if (!text || text.length < 2) return true;
  if (isSymbolOnly(text)) return true;
  // Only digits/punctuation
  if (/^[\d\s\p{P}]+$/u.test(text)) return true;
  return false;
}

/**
 * Attempt to repair a broken subtitle line by removing common
 * mid-word-break artifacts produced by auto-captioners.
 */
export function repairBrokenLine(text: string): string {
  let t = text;
  // Remove leading lowercase continuation marker
  t = t.replace(/^[a-z]{1,3}\s+/, (m) =>
    // Keep if it's a real word (3+ chars after), otherwise drop
    m.trim().length >= 3 ? m : ""
  );
  return t.trim();
}
