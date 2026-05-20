import { describe, it, expect } from "vitest";
import { clean } from "../src/pipeline.js";
import type { RawSegment } from "../src/types.js";

function raw(text: string, start: number, duration = 1.0): RawSegment {
  return { text, start, duration };
}

describe("clean — Japanese", () => {
  it("removes bracket noise and fillers", () => {
    const input = [
      raw("[音楽]", 0),
      raw("えっと今日は", 1),
      raw("機械学習について", 2),
      raw("話します", 3),
    ];
    const { segments, stats } = clean(input, { language: "ja" });
    const allText = segments.map((s) => s.text).join(" ");
    expect(allText).not.toContain("[音楽]");
    expect(allText).not.toContain("えっと");
    expect(allText).toContain("機械学習");
    expect(stats.inputSegments).toBe(4);
  });

  it("merges fragmented utterances", () => {
    const input = [
      raw("今日は", 0, 0.4),
      raw("機械学習", 0.4, 0.4),
      raw("について話します", 0.8, 0.8),
    ];
    const { segments, stats } = clean(input, {
      language: "ja",
      mergeGapSec: 1.0,
    });
    // Should be merged to fewer segments
    expect(segments.length).toBeLessThan(input.length);
    expect(stats.mergedCount).toBeGreaterThan(0);
  });

  it("removes near-duplicate auto-caption artifacts", () => {
    const input = [
      raw("機械学習について", 0),
      raw("機械学習について話します", 3),
      raw("機械学習について", 6), // repeated
      raw("全く別のトピック", 10),
    ];
    const { segments, stats } = clean(input, { language: "ja", mergeGapSec: 0.5 });
    expect(stats.removedDuplicates).toBeGreaterThan(0);
    expect(segments.length).toBeLessThan(4);
  });
});

describe("clean — English", () => {
  it("removes English fillers", () => {
    const input = [
      raw("um so machine learning is", 0),
      raw("uh basically a subset of", 1.5),
      raw("artificial intelligence you know", 3),
    ];
    const { segments } = clean(input, { language: "en" });
    const allText = segments.map((s) => s.text).join(" ");
    expect(allText).not.toContain(" um ");
    expect(allText).not.toContain(" uh ");
    expect(allText).toContain("machine learning");
  });

  it("filters pure noise segments", () => {
    const input = [
      raw("ok", 0, 0.3),           // too short
      raw("...", 1, 0.3),          // symbols
      raw("um uh er", 2, 0.5),     // all fillers
      raw("machine learning is transforming every industry", 3, 2),
    ];
    const { segments } = clean(input, { language: "en" });
    expect(segments.length).toBe(1);
    expect(segments[0]?.text).toContain("machine learning");
  });
});

describe("clean — stats", () => {
  it("returns correct compression ratio", () => {
    const input = Array.from({ length: 10 }, (_, i) =>
      raw(`segment number ${i} with content`, i * 2)
    );
    const { stats } = clean(input, { language: "en" });
    expect(stats.compressionRatio).toBeGreaterThan(0);
    expect(stats.compressionRatio).toBeLessThanOrEqual(1);
    expect(stats.inputSegments).toBe(10);
  });

  it("handles empty input", () => {
    const { segments, stats } = clean([]);
    expect(segments).toEqual([]);
    expect(stats.inputSegments).toBe(0);
    expect(stats.compressionRatio).toBe(0);
  });
});

describe("clean — auto language detection", () => {
  it("handles mixed-language input", () => {
    const input = [
      raw("機械学習について話します", 0),
      raw("machine learning is important", 3),
    ];
    const { segments } = clean(input, { language: "auto" });
    expect(segments.length).toBeGreaterThan(0);
  });
});
