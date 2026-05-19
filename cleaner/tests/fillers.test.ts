import { describe, it, expect } from "vitest";
import { removeJaFillers, removeEnFillers, fillerRatio, removeBracketNoise } from "../src/fillers.js";

describe("removeJaFillers", () => {
  it("removes hesitation sounds", () => {
    const result = removeJaFillers("えっと今日は機械学習について話します");
    expect(result).not.toContain("えっと");
    expect(result).toContain("機械学習");
  });

  it("removes なんか", () => {
    const result = removeJaFillers("なんか面白いですね");
    expect(result).not.toContain("なんか");
  });

  it("removes あー hesitation", () => {
    const result = removeJaFillers("あー今日はとてもいい天気ですね");
    expect(result).not.toContain("あー");
    expect(result).toContain("今日は");
  });

  it("collapses repeated phrase boundary", () => {
    const result = removeJaFillers("機械機械機械学習");
    expect(result).not.toMatch(/機械{3}/);
  });
});

describe("removeEnFillers", () => {
  it("removes um and uh", () => {
    const result = removeEnFillers("um so uh this is machine learning");
    expect(result).not.toContain("um");
    expect(result).not.toContain("uh");
    expect(result).toContain("machine learning");
  });

  it("removes 'you know'", () => {
    const result = removeEnFillers("it is, you know, really important");
    expect(result).not.toContain("you know");
  });

  it("removes 'like' as filler but keeps content", () => {
    const result = removeEnFillers("this is like really interesting");
    expect(result).not.toContain(" like ");
    expect(result).toContain("interesting");
  });

  it("removes leading discourse markers", () => {
    const result = removeEnFillers("so basically this is how it works");
    expect(result.trimStart()).not.toMatch(/^so\b/i);
  });
});

describe("fillerRatio", () => {
  it("returns high ratio for filler-heavy text", () => {
    const ratio = fillerRatio("えっとあーなんかまあそのーちょっと", "ja");
    expect(ratio).toBeGreaterThan(0.3);
  });

  it("returns low ratio for clean text", () => {
    const ratio = fillerRatio("機械学習は人工知能の重要な分野です", "ja");
    expect(ratio).toBeLessThan(0.1);
  });

  it("handles empty string", () => {
    expect(fillerRatio("", "en")).toBe(0);
    expect(fillerRatio("", "ja")).toBe(0);
  });
});

describe("removeBracketNoise", () => {
  it("removes square bracket annotations", () => {
    // Raw function returns without trimming — normalize() handles whitespace
    expect(removeBracketNoise("[Music] hello").trim()).toBe("hello");
    expect(removeBracketNoise("[Applause]").trim()).toBe("");
  });

  it("removes Japanese bracket annotations", () => {
    expect(removeBracketNoise("【拍手】ありがとう").trim()).toBe("ありがとう");
  });

  it("removes music symbols", () => {
    expect(removeBracketNoise("♪ song ♪ and text").trim()).toBe("and text");
  });
});
