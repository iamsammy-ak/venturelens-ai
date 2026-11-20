"""Runtime settings: API key and model list, read from env vars, a .env file or Streamlit secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Free OpenRouter models, tried in order. Override with OPENROUTER_MODELS (comma-separated).
DEFAULT_MODELS: tuple[str, ...] = (
    "nvidia/nemotron-3.5-super-vl:free",
    "google/gemma-4-26b-a4b-it:free",
    "inclusionai/ling-3.2-flash:free",
    "google/gemma-4-31b-it:free",
)


@dataclass(frozen=True)
class Settings:
    api_key: str | None = None
    models: tuple[str, ...] = DEFAULT_MODELS

    @property
    def live(self) -> bool:
        """True when a key is configured and the app can call a model."""
        return bool(self.api_key)


def _secret(name: str) -> str | None:
    """Read a Streamlit secret without failing when no secrets file exists."""
    try:
        import streamlit as st

        value = st.secrets.get(name)
    except Exception:  # no secrets file, or not running under Streamlit
        return None
    return str(value) if value else None


def load_settings() -> Settings:
    load_dotenv(override=False)
    key = os.getenv("OPENROUTER_API_KEY") or _secret("OPENROUTER_API_KEY") or ""
    raw_models = os.getenv("OPENROUTER_MODELS") or _secret("OPENROUTER_MODELS") or ""
    models = tuple(m.strip() for m in raw_models.split(",") if m.strip()) or DEFAULT_MODELS
    return Settings(api_key=key.strip() or None, models=models)
