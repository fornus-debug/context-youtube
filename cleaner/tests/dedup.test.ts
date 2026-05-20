import { describe, it, expect } from "vitest";
import { deduplicateSegments } from "../src/dedup.js";

function segs(texts: string[]) {
  return texts.map((text) => ({ text, start: 0, end: 1 }));
}

describe("deduplicateSegments", () => {
  it("removes exact duplicates", () => {
    const input = segs([
      "machine learning is important",
      "machine learning is important",
      "something else entirely",
    ]);
    const { segments, removedCount } = deduplicateSegments(input, 0.72);
    expect(removedCount).toBe(1);
    expect(segments.length).toBe(2);
  });

  it("removes near-duplicates above threshold", () => {
    // String 2 is string 1 with "data" inserted — high trigram overlap
    const input = segs([
      "this is about machine learning algorithms for classification",
      "this is about machine learning algorithms for data classification",
      "completely different content about cooking pasta recipes",
    ]);
    const { segments, removedCount } = deduplicateSegments(input, 0.72);
    expect(removedCount).toBeGreaterThanOrEqual(1);
    expect(segments.length).toBeLessThan(3);
  });

  it("keeps semantically different segments", () => {
    const input = segs([
      "machine learning algorithms for classification",
      "cooking pasta with tomato sauce",
      "quantum physics and entanglement",
      "javascript frontend development",
    ]);
    const { segments } = deduplicateSegments(input, 0.72);
    expect(segments.length).toBe(4);
  });

  it("handles empty input", () => {
    const { segments, removedCount } = deduplicateSegments([], 0.72);
    expect(segments).toEqual([]);
    expect(removedCount).toBe(0);
  });

  it("handles single segment", () => {
    const { segments } = deduplicateSegments(segs(["hello world"]), 0.72);
    expect(segments.length).toBe(1);
  });

  it("removes repeated caption artifacts", () => {
    // YouTube auto-captions often repeat the same line multiple times
    const input = segs([
      "gradient descent optimization",
      "gradient descent optimization technique",
      "gradient descent optimization",
    ]);
    const { segments } = deduplicateSegments(input, 0.72);
    expect(segments.length).toBeLessThan(3);
  });
});
