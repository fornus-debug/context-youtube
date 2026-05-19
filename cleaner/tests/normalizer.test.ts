import { describe, it, expect } from "vitest";
import { normalize, detectLang, endsWithSentence, isUnrecoverable } from "../src/normalizer.js";

describe("normalize", () => {
  it("converts full-width chars to half-width via NFKC", () => {
    expect(normalize("Ａ１２３")).toBe("A123");
  });

  it("removes bracket noise", () => {
    expect(normalize("[Music] hello")).toBe("hello");
    expect(normalize("【拍手】ありがとう")).toBe("ありがとう");
  });

  it("collapses repeated punctuation", () => {
    expect(normalize("すごい!!!")).toBe("すごい!");
    expect(normalize("really???")).toBe("really?");
  });

  it("collapses repeated words in English", () => {
    expect(normalize("machine machine machine learning")).toBe("machine learning");
  });

  it("collapses repeated Japanese phrases", () => {
    expect(normalize("機械学習機械学習機械学習について")).toBe("機械学習について");
  });

  it("removes control characters", () => {
    expect(normalize("hello\x00world")).toBe("helloworld");
  });

  it("normalizes whitespace", () => {
    expect(normalize("hello   world")).toBe("hello world");
  });

  it("removes orphan hyphens", () => {
    expect(normalize("- learning is fun")).toBe("learning is fun");
  });
});

describe("detectLang", () => {
  it("detects Japanese text", () => {
    expect(detectLang("機械学習について話します")).toBe("ja");
    expect(detectLang("今日はいい天気ですね")).toBe("ja");
  });

  it("detects English text", () => {
    expect(detectLang("machine learning is amazing")).toBe("en");
    expect(detectLang("hello world this is a test")).toBe("en");
  });

  it("detects mixed text by CJK ratio", () => {
    // >25% CJK: "AIと機械学習について" has 7 CJK out of 12 non-space chars ≈ 58%
    expect(detectLang("AIと機械学習について")).toBe("ja");
    // <25% CJK: no CJK at all
    expect(detectLang("Using AI technology and ML")).toBe("en");
  });
});

describe("endsWithSentence", () => {
  it("detects Japanese sentence endings", () => {
    expect(endsWithSentence("話します。", "ja")).toBe(true);
    expect(endsWithSentence("どうですか？", "ja")).toBe(true);
    expect(endsWithSentence("話します", "ja")).toBe(false);
  });

  it("detects English sentence endings", () => {
    expect(endsWithSentence("That's correct.", "en")).toBe(true);
    expect(endsWithSentence("Really?", "en")).toBe(true);
    expect(endsWithSentence("machine learning", "en")).toBe(false);
  });
});

describe("isUnrecoverable", () => {
  it("rejects empty and single-char strings", () => {
    expect(isUnrecoverable("")).toBe(true);
    expect(isUnrecoverable("a")).toBe(true);
  });

  it("rejects symbol-only strings", () => {
    expect(isUnrecoverable("...")).toBe(true);
    expect(isUnrecoverable("---")).toBe(true);
  });

  it("accepts valid text", () => {
    expect(isUnrecoverable("hello world")).toBe(false);
    expect(isUnrecoverable("機械学習")).toBe(false);
  });
});
