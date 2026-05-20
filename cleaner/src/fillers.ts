/**
 * Filler word lists and removal logic.
 *
 * Strategy:
 *   Japanese — no word boundaries; match patterns with surrounding context
 *   English  — word-boundary regex; handle contractions
 *
 * These fillers add zero semantic value to embeddings, so we remove them
 * aggressively before any vectorization.
 */

// ── Japanese fillers ─────────────────────────────────────────────────────────

// Standalone hesitation sounds (appear alone or at utterance start/end)
const JA_HESITATIONS = [
  "あー+", "えー+", "うー+", "おー+", "んー+",
  "あのー*", "そのー*", "えっと", "えーと", "うーん",
];

// Mid-sentence fillers that appear before/after content
const JA_FILLERS = [
  "なんか", "まあ", "ちょっと", "やっぱり", "やっぱ",
  "要するに", "いわゆる", "つまり", "そういう",
  "みたいな", "っていうか", "というか", "みたいに",
  "ですね", "ですよね", "ですよ", "じゃないですか",
];

// Discourse markers that add no content at boundaries
const JA_DISCOURSE = [
  "じゃあ", "それで", "それから", "そして", "でも",
  "ところで", "ちなみに",
];

// Repetition artifacts (auto-caption often repeats the same phrase)
const JA_REPEATED_BOUNDARY = /([^\s]{2,10})\1{2,}/g;

// Build combined Japanese filler regex (applied inside sentences)
const JA_FILLER_RE = new RegExp(
  `(${[...JA_HESITATIONS, ...JA_FILLERS].join("|")})`,
  "g"
);

const JA_DISCOURSE_BOUNDARY_RE = new RegExp(
  `^(${JA_DISCOURSE.join("|")})[、。]?`,
  "u"
);

// ── English fillers ──────────────────────────────────────────────────────────

const EN_HESITATION_RE =
  /\b(um+|uh+|er+|ah+|hmm+|huh|mhm)\b[,.]?/gi;

const EN_FILLER_RE =
  /\b(like|you know|i mean|kind of|sort of|basically|literally|actually|right\?|okay so|alright so|so basically|anyway|you see|i guess|i think|to be honest|honestly|frankly)\b/gi;

const EN_DISCOURSE_RE =
  /^(so|well|now|okay|right|alright|anyway)[,\s]+/gi;

// ── Bracket/annotation noise ─────────────────────────────────────────────────

// YouTube auto-generated annotations
const BRACKET_NOISE_RE =
  /[\[【《〔].*?[\]】》〕]|\(.*?\)|♪.*?♪|&[a-z]+;|<[^>]+>/g;

// Lone punctuation / symbols with no surrounding words
const SYMBOL_ONLY_RE = /^[\s\p{P}\p{S}]+$/u;

// ── Public API ───────────────────────────────────────────────────────────────

export function removeBracketNoise(text: string): string {
  // Replace with empty string; surrounding whitespace is collapsed by normalize()
  return text.replace(BRACKET_NOISE_RE, "");
}

export function removeJaFillers(text: string): string {
  let t = text;
  t = t.replace(JA_FILLER_RE, "");
  t = t.replace(JA_DISCOURSE_BOUNDARY_RE, "");
  t = t.replace(JA_REPEATED_BOUNDARY, "$1");
  return t;
}

export function removeEnFillers(text: string): string {
  let t = text;
  t = t.replace(EN_HESITATION_RE, "");
  t = t.replace(EN_FILLER_RE, "");
  t = t.replace(EN_DISCOURSE_RE, "");
  return t;
}

export function isSymbolOnly(text: string): boolean {
  return SYMBOL_ONLY_RE.test(text);
}

/**
 * Count filler tokens in `text` to produce a filler-ratio metric.
 * Used by the noise scorer — does not modify text.
 */
export function fillerRatio(text: string, lang: "ja" | "en"): number {
  if (!text) return 0;
  const totalChars = text.replace(/\s/g, "").length;
  if (totalChars === 0) return 0;

  let fillerChars = 0;
  if (lang === "ja") {
    for (const m of text.matchAll(new RegExp(JA_FILLER_RE.source, "g"))) {
      fillerChars += m[0].length;
    }
  } else {
    for (const re of [EN_HESITATION_RE, EN_FILLER_RE]) {
      for (const m of text.matchAll(new RegExp(re.source, "gi"))) {
        fillerChars += m[0].length;
      }
    }
  }
  return Math.min(fillerChars / totalChars, 1.0);
}
