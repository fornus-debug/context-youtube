import { describe, it, expect } from "vitest";
import { mergeSegments } from "../src/merger.js";
import type { WorkSegment } from "../src/types.js";

function seg(text: string, start: number, duration: number = 1, lang: "ja" | "en" = "ja"): WorkSegment {
  return { text, start, end: start + duration, duration, lang, originalCount: 1, noiseScore: 0 };
}

describe("mergeSegments", () => {
  it("merges adjacent Japanese fragments within gap", () => {
    const segments = [
      seg("今日は", 0, 0.5, "ja"),
      seg("機械学習", 0.5, 0.5, "ja"),
      seg("について話します", 1.0, 1.0, "ja"),
    ];
    const result = mergeSegments(segments, 1.8);
    expect(result.length).toBeLessThan(3);
    expect(result[0]?.text).toContain("機械学習");
  });

  it("does not merge when gap exceeds threshold", () => {
    const segments = [
      seg("first sentence.", 0, 1, "en"),
      seg("second sentence", 5, 1, "en"), // 4s gap
    ];
    const result = mergeSegments(segments, 1.8);
    expect(result.length).toBe(2);
  });

  it("stops merge at English sentence boundary", () => {
    const segments = [
      seg("This is complete.", 0, 1, "en"),
      seg("new topic here", 1.1, 1, "en"),
    ];
    const result = mergeSegments(segments, 1.8);
    expect(result.length).toBe(2);
  });

  it("stops merge at Japanese sentence boundary", () => {
    const segments = [
      seg("これで完了です。", 0, 1, "ja"),
      seg("次のトピック", 1.1, 1, "ja"),
    ];
    const result = mergeSegments(segments, 1.8);
    expect(result.length).toBe(2);
  });

  it("tracks originalCount through merges", () => {
    const segments = [
      seg("今日は", 0, 0.4, "ja"),
      seg("面白い", 0.4, 0.4, "ja"),
      seg("ですね", 0.8, 0.4, "ja"),
    ];
    const result = mergeSegments(segments, 1.8);
    // All three should merge into one
    expect(result[0]?.originalCount).toBeGreaterThanOrEqual(2);
  });

  it("merges English continuation (starts lowercase)", () => {
    const segments = [
      seg("machine learning", 0, 0.8, "en"),
      seg("is very powerful", 0.9, 0.8, "en"),
    ];
    const result = mergeSegments(segments, 1.8);
    expect(result.length).toBe(1);
    expect(result[0]?.text).toContain("machine learning");
    expect(result[0]?.text).toContain("is very powerful");
  });

  it("handles empty input", () => {
    expect(mergeSegments([], 1.8)).toEqual([]);
  });

  it("handles single segment", () => {
    const result = mergeSegments([seg("hello", 0)], 1.8);
    expect(result.length).toBe(1);
  });
});
