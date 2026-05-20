/**
 * Semantic deduplication using character n-gram Jaccard similarity.
 *
 * Why character n-grams:
 *   - Works for Japanese without a tokenizer (no word segmentation needed)
 *   - More robust than word-level for CJK + Latin mixed text
 *   - n=3 gives good precision/recall tradeoff
 *
 * Algorithm:
 *   1. Normalize text for comparison (strip punctuation, lowercase)
 *   2. Build character 3-gram shingle set
 *   3. For each new segment, compute Jaccard against all accepted segments
 *   4. If max similarity ≥ threshold → drop as near-duplicate
 *
 * Sliding window (WINDOW_SIZE) limits O(n²) to O(n·k) where k is window,
 * since duplicates in YouTube captions are almost always adjacent.
 */

const N_GRAM_SIZE = 3;
const WINDOW_SIZE = 20;

function normalizeForCompare(text: string): string {
  return text
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[\p{P}\p{S}\s]/gu, "");
}

function shingles(text: string): Set<string> {
  const s = new Set<string>();
  const norm = normalizeForCompare(text);
  for (let i = 0; i <= norm.length - N_GRAM_SIZE; i++) {
    s.add(norm.slice(i, i + N_GRAM_SIZE));
  }
  return s;
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0;
  let intersection = 0;
  for (const item of a) {
    if (b.has(item)) intersection++;
  }
  return intersection / (a.size + b.size - intersection);
}

/**
 * Exact-duplicate detection via normalized hash.
 * O(1) per check; run before Jaccard to skip expensive computation.
 */
function exactKey(text: string): string {
  return normalizeForCompare(text);
}

export interface DedupResult<T extends { text: string }> {
  segments: T[];
  removedCount: number;
}

export function deduplicateSegments<T extends { text: string }>(
  segments: T[],
  threshold: number
): DedupResult<T> {
  const accepted: T[] = [];
  const acceptedShingles: Set<string>[] = [];
  const exactSeen = new Set<string>();
  let removedCount = 0;

  for (const seg of segments) {
    const key = exactKey(seg.text);

    // 1. Exact duplicate check (O(1))
    if (exactSeen.has(key)) {
      removedCount++;
      continue;
    }

    // 2. Near-duplicate check within sliding window (O(k))
    const segShingles = shingles(seg.text);
    const windowStart = Math.max(0, acceptedShingles.length - WINDOW_SIZE);
    let isDup = false;

    for (let i = windowStart; i < acceptedShingles.length; i++) {
      const ref = acceptedShingles[i];
      if (ref !== undefined && jaccard(segShingles, ref) >= threshold) {
        isDup = true;
        break;
      }
    }

    if (isDup) {
      removedCount++;
    } else {
      accepted.push(seg);
      acceptedShingles.push(segShingles);
      exactSeen.add(key);
    }
  }

  return { segments: accepted, removedCount };
}
