import { describe, it, expect } from "vitest";
import { scoreNoise, explainNoise } from "../src/noise.js";

describe("scoreNoise", () => {
  it("scores clean semantic content low", () => {
    const score = scoreNoise("機械学習は人工知能の重要な分野です。", "ja");
    expect(score).toBeLessThan(0.35);
  });

  it("scores filler-heavy text high", () => {
    // All tokens are Japanese fillers → filler ratio ≈ 1.0
    const score = scoreNoise("えっとあーなんかそのーまあちょっと", "ja");
    expect(score).toBeGreaterThan(0.5);
  });

  it("scores very short text high", () => {
    // 2-char segment: dominated by length + incompleteness penalties
    const score = scoreNoise("ok", "en");
    expect(score).toBeGreaterThan(0.4);
  });

  it("scores repeated words higher than clean content", () => {
    // Repetition score is non-trivial; must exceed a clean sentence
    const cleanScore = scoreNoise(
      "machine learning transforms how we process data.",
      "en"
    );
    const repeatScore = scoreNoise("yes yes yes yes yes yes okay", "en");
    expect(repeatScore).toBeGreaterThan(cleanScore);
    expect(repeatScore).toBeGreaterThan(0.05);
  });

  it("scores symbol-only content high", () => {
    // "..." has no word chars → endsWithSentence = false → high incompleteness
    // plus unicode noise and length penalty
    const score = scoreNoise("...", "en");
    expect(score).toBeGreaterThan(0.44);
  });

  it("scores clean English content low", () => {
    const score = scoreNoise(
      "Neural networks are a subset of machine learning that use layers of neurons.",
      "en"
    );
    expect(score).toBeLessThan(0.3);
  });
});

describe("explainNoise", () => {
  it("returns all factor keys", () => {
    const factors = explainNoise("hello world", "en");
    expect(factors).toHaveProperty("fillerRatio");
    expect(factors).toHaveProperty("repetitionScore");
    expect(factors).toHaveProperty("lengthPenalty");
    expect(factors).toHaveProperty("incompletenessScore");
    expect(factors).toHaveProperty("unicodeNoiseScore");
    expect(factors).toHaveProperty("total");
  });

  it("all factor values are between 0 and 1", () => {
    const factors = explainNoise("um like you know basically", "en");
    for (const [key, value] of Object.entries(factors)) {
      expect(value, `${key} out of range`).toBeGreaterThanOrEqual(0);
      expect(value, `${key} out of range`).toBeLessThanOrEqual(1);
    }
  });
});
