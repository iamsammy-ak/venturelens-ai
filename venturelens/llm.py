"""OpenRouter client with model fallback, retries, JSON validation and an on-disk cache.

Free OpenRouter models are rate limited, so every successful answer is cached by a hash of
the request: re-running the same analysis costs no extra model calls.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .config import Settings, load_settings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_CACHE_DIR = Path(".cache") / "llm"
T = TypeVar("T", bound=BaseModel)

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_FENCE = re.compile(r"```(?:json|markdown|md)?\s*(.*?)```", re.S | re.I)


class LLMError(RuntimeError):
    """No configured model produced a usable answer."""


def clean_text(text: str) -> str:
    """Drop reasoning tags and a wrapping code fence from a free-text reply."""
    text = _THINK.sub("", text or "").strip()
    fenced = _FENCE.fullmatch(text)
    return fenced.group(1).strip() if fenced else text


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply (handles fences, prose and reasoning tags)."""
    text = _THINK.sub("", text or "").strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in the model reply") from None
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("the model reply is JSON but not an object")
    return value


class LLMClient:
    """Calls OpenRouter's OpenAI-compatible API, trying each configured model in turn."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        app_name: str = "VentureLens AI",
        cache_dir: Path | None = DEFAULT_CACHE_DIR,
        timeout: float = 120.0,
    ) -> None:
        self.settings = settings or load_settings()
        if not self.settings.api_key:
            raise LLMError("OPENROUTER_API_KEY is not set.")
        from openai import OpenAI

        self._client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=self.settings.api_key,
            default_headers={"X-Title": app_name},
            timeout=timeout,
            max_retries=0,
        )
        self.cache_dir = cache_dir
        self.last_model: str | None = None
        self.last_errors: list[str] = []
        self.calls_made = 0

    # ------------------------------------------------------------------ cache
    def _cache_file(self, messages: list[dict], json_mode: bool, temperature: float) -> Path | None:
        if self.cache_dir is None:
            return None
        key = {"models": list(self.settings.models), "messages": messages, "json": json_mode, "t": temperature}
        digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode("utf-8")).hexdigest()[:40]
        return self.cache_dir / f"{digest}.json"

    # ------------------------------------------------------------------- chat
    def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.3,
        max_tokens: int = 3000,
    ) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        path = self._cache_file(messages, json_mode, temperature)
        if path and path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            self.last_model = cached.get("model")
            return cached["content"]
        content, model = self._call_with_fallback(messages, json_mode, temperature, max_tokens)
        self.last_model = model
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"model": model, "content": content}), encoding="utf-8")
        return content

    def forget(self, system: str, user: str, *, json_mode: bool = False, temperature: float = 0.3) -> None:
        """Remove a cached answer (used when a cached reply turns out to be unusable)."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        path = self._cache_file(messages, json_mode, temperature)
        if path and path.exists():
            path.unlink()

    def _call_with_fallback(
        self, messages: list[dict], json_mode: bool, temperature: float, max_tokens: int
    ) -> tuple[str, str]:
        """Try each model once; a busy or failing model is skipped rather than retried, which
        saves the daily free-tier quota. Models that were only busy get a second pass."""
        from openai import APIConnectionError, APIStatusError, RateLimitError

        self.last_errors = []
        retryable: list[str] = []
        for round_ in range(2):
            candidates = list(self.settings.models) if round_ == 0 else retryable
            if round_ == 1:
                if not retryable:
                    break
                time.sleep(6)
            retryable = []
            for model in candidates:
                use_json_format = json_mode
                for _ in range(2):  # second pass only when JSON mode itself was rejected
                    kwargs: dict = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if use_json_format:
                        kwargs["response_format"] = {"type": "json_object"}
                    try:
                        self.calls_made += 1
                        response = self._client.chat.completions.create(**kwargs)
                    except RateLimitError as exc:
                        if "per-day" in str(exc) or "per day" in str(exc):
                            raise LLMError(
                                "OpenRouter's daily free-model limit is used up. Try again tomorrow, "
                                "or add credits to raise the limit."
                            ) from exc
                        self.last_errors.append(f"{model}: busy (HTTP 429)")
                        retryable.append(model)
                        break
                    except APIConnectionError as exc:  # includes timeouts
                        self.last_errors.append(f"{model}: {type(exc).__name__}")
                        retryable.append(model)
                        break
                    except APIStatusError as exc:
                        self.last_errors.append(f"{model}: HTTP {exc.status_code} {str(exc)[:160]}")
                        if exc.status_code == 401:
                            raise LLMError("OpenRouter rejected the API key (HTTP 401).") from exc
                        if exc.status_code == 400 and use_json_format:
                            use_json_format = False
                            continue
                        if exc.status_code >= 500:
                            retryable.append(model)
                        break
                    choices = getattr(response, "choices", None) or []
                    choice = choices[0] if choices else None
                    content = ((choice.message.content if choice else None) or "").strip()
                    if json_mode and getattr(choice, "finish_reason", None) == "length":
                        self.last_errors.append(f"{model}: reply cut off at the token limit")
                        break
                    if content:
                        return content, model
                    self.last_errors.append(f"{model}: empty reply")
                    break
        raise LLMError("No model returned an answer. " + "; ".join(self.last_errors[-6:]))

    # ------------------------------------------------------------ structured
    def complete_json(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        temperature: float = 0.2,
        max_tokens: int = 8000,
    ) -> T:
        """Ask for JSON matching `schema`; one repair round-trip if the first reply is invalid."""
        schema_hint = json.dumps(schema.model_json_schema(), separators=(",", ":"))
        system_prompt = (
            f"{system}\n\nReply with one JSON object only: no prose and no code fences. "
            f"It must validate against this JSON Schema:\n{schema_hint}"
        )
        raw = self.chat(system_prompt, user, json_mode=True, temperature=temperature, max_tokens=max_tokens)
        try:
            return schema.model_validate(extract_json(raw))
        except (ValueError, ValidationError) as first_error:
            self.forget(system_prompt, user, json_mode=True, temperature=temperature)
            repair = (
                f"{user}\n\nYour previous reply could not be used ({str(first_error)[:500]}). "
                "Return the corrected JSON object only."
            )
            raw = self.chat(system_prompt, repair, json_mode=True, temperature=0.0, max_tokens=max_tokens)
            try:
                return schema.model_validate(extract_json(raw))
            except (ValueError, ValidationError) as exc:
                self.forget(system_prompt, repair, json_mode=True, temperature=0.0)
                raise LLMError(f"The model's reply did not match the expected format: {exc}") from exc
