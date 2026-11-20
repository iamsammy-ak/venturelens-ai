"""Sample ideas and saved AI analyses, so the app works without an API key."""

from __future__ import annotations

import json
from pathlib import Path

from .finance import Assumptions, MarketInputs
from .schemas import IdeaInput

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"
ANALYSES_DIR = DEMO_DIR / "analyses"


def load_samples() -> list[dict]:
    return json.loads((DEMO_DIR / "samples.json").read_text(encoding="utf-8"))


def sample_inputs(sample: dict) -> tuple[IdeaInput, Assumptions, MarketInputs]:
    return (
        IdeaInput(**sample["idea"]),
        Assumptions(**sample["assumptions"]),
        MarketInputs(**sample["market"]),
    )


def load_saved_analysis(fingerprint: str) -> dict | None:
    path = ANALYSES_DIR / f"{fingerprint}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_analysis(analysis: dict) -> Path:
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
    path = ANALYSES_DIR / f"{analysis['fingerprint']}.json"
    path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
