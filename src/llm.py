"""
LLM provider abstraction.

Set LLM_PROVIDER in .env to switch (default: anthropic):

  LLM_PROVIDER=anthropic   Claude Haiku (extract) + Sonnet (answer)
  LLM_PROVIDER=gemini      Gemini 1.5 Flash — free tier (1500 req/day)
  LLM_PROVIDER=groq        Groq Llama 3.3 70B — free tier (14,400 req/day)

All providers expose the same interface:
  get_extract_client() → LLMClient  (cheap/fast model for extraction)
  get_answer_client()  → LLMClient  (quality model for final answer)
"""

import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# ── Response ──────────────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float  # 0.0 for free-tier providers

# ── Client protocol ───────────────────────────────────────────────────────────

@runtime_checkable
class LLMClient(Protocol):
    model: str

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
    ) -> LLMResponse: ...

# ── Provider: Anthropic ───────────────────────────────────────────────────────

_ANTHROPIC_PRICES = {
    "claude-haiku-4-5-20251001": (0.25, 1.25),   # $/MTok in/out
    "claude-sonnet-4-6":         (3.00, 15.00),
}

class AnthropicClient:
    def __init__(self, model: str) -> None:
        import anthropic as _anthropic
        self.model = model
        self._client = _anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._prices = _ANTHROPIC_PRICES.get(model, (3.0, 15.0))

    def complete(self, system: str, user: str, max_tokens: int = 2048) -> LLMResponse:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        i_tok = resp.usage.input_tokens
        o_tok = resp.usage.output_tokens
        cost = (i_tok / 1e6 * self._prices[0]) + (o_tok / 1e6 * self._prices[1])
        return LLMResponse(
            text=resp.content[0].text,
            input_tokens=i_tok,
            output_tokens=o_tok,
            cost_usd=cost,
        )

# ── Provider: Google Gemini ───────────────────────────────────────────────────

class GeminiClient:
    def __init__(self, model: str = "gemini-1.5-flash") -> None:
        import google.generativeai as genai
        self.model = model
        self._genai = genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    def complete(self, system: str, user: str, max_tokens: int = 2048) -> LLMResponse:
        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system,
        )
        resp = model.generate_content(
            user,
            generation_config={"max_output_tokens": max_tokens},
        )
        usage = resp.usage_metadata
        i_tok = getattr(usage, "prompt_token_count", 0) or 0
        o_tok = getattr(usage, "candidates_token_count", 0) or 0
        return LLMResponse(
            text=resp.text,
            input_tokens=i_tok,
            output_tokens=o_tok,
            cost_usd=0.0,  # free tier
        )

# ── Provider: Groq ────────────────────────────────────────────────────────────

class GroqClient:
    def __init__(self, model: str = "llama-3.3-70b-versatile") -> None:
        from groq import Groq
        self.model = model
        self._client = Groq(api_key=os.environ["GROQ_API_KEY"])

    def complete(self, system: str, user: str, max_tokens: int = 2048) -> LLMResponse:
        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        i_tok = resp.usage.prompt_tokens
        o_tok = resp.usage.completion_tokens
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            input_tokens=i_tok,
            output_tokens=o_tok,
            cost_usd=0.0,  # free tier
        )

# ── Factory ───────────────────────────────────────────────────────────────────

_EXTRACT_MODELS: dict[str, str] = {
    "anthropic": "claude-haiku-4-5-20251001",
    "gemini":    "gemini-1.5-flash",
    "groq":      "llama-3.3-70b-versatile",
}

_ANSWER_MODELS: dict[str, str] = {
    "anthropic": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
    "gemini":    "gemini-1.5-flash",
    "groq":      "llama-3.3-70b-versatile",
}

def _provider() -> str:
    return os.getenv("LLM_PROVIDER", "anthropic").lower()

def _make(model: str) -> LLMClient:
    p = _provider()
    if p == "gemini":
        return GeminiClient(model)  # type: ignore[return-value]
    if p == "groq":
        return GroqClient(model)    # type: ignore[return-value]
    return AnthropicClient(model)   # type: ignore[return-value]

def get_extract_client() -> LLMClient:
    model = os.getenv("EXTRACT_MODEL", _EXTRACT_MODELS[_provider()])
    return _make(model)

def get_answer_client() -> LLMClient:
    model = os.getenv("ANSWER_MODEL", _ANSWER_MODELS[_provider()])
    return _make(model)

def provider_label() -> str:
    """Human-readable label for logging."""
    p = _provider()
    if p == "gemini":
        return "Gemini 1.5 Flash (free)"
    if p == "groq":
        return "Groq Llama 3.3 70B (free)"
    return "Claude (paid)"
