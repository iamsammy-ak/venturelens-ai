"""Glue between the deterministic model and the AI agents, shared by the app and scripts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import pandas as pd

from .agents import SupportsLLM, assess_idea, write_memo
from .finance import (
    Assumptions,
    MarketInputs,
    MarketSize,
    ProjectionSummary,
    UnitEconomics,
    market_size,
    project,
    sensitivity,
    summarize,
    unit_economics,
)
from .formatting import money, month_label, months, pct, ratio
from .schemas import IdeaInput
from .scoring import Scorecard, build_scorecard


@dataclass(frozen=True)
class Computed:
    unit: UnitEconomics
    market: MarketSize
    projection: pd.DataFrame
    summary: ProjectionSummary
    sensitivity: pd.DataFrame


def compute(a: Assumptions, m: MarketInputs) -> Computed:
    df = project(a)
    return Computed(unit_economics(a), market_size(m, a), df, summarize(df, a), sensitivity(a))


def _normalise(value):
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    return value


def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(_normalise(payload), sort_keys=True).encode("utf-8")).hexdigest()[:16]


def idea_fingerprint(idea: IdeaInput) -> str:
    return _digest({"idea": idea.model_dump()})


def fingerprint(idea: IdeaInput, a: Assumptions, m: MarketInputs) -> str:
    return _digest({"idea": idea.model_dump(), "assumptions": asdict(a), "market": asdict(m)})


def memo_facts(a: Assumptions, c: Computed, card: Scorecard) -> dict:
    s = c.summary
    return {
        "assumptions": {
            "revenue per customer per month": money(a.arpu_monthly),
            "gross margin": pct(a.gross_margin, 0),
            "customer acquisition cost": money(a.cac),
            "monthly churn": pct(a.monthly_churn),
            "fixed costs per month at launch": money(a.fixed_costs_monthly),
            "starting cash": money(a.starting_cash),
            "projection horizon": f"{a.months} months",
        },
        "unit economics": {
            "customer lifetime value (LTV)": money(c.unit.ltv),
            "LTV to CAC": ratio(c.unit.ltv_to_cac),
            "CAC payback": months(c.unit.payback_months),
        },
        "market (bottom-up)": {
            "TAM": money(c.market.tam),
            "SAM": money(c.market.sam),
            "SOM": money(c.market.som),
        },
        "projection": {
            "sustained break-even": month_label(s.break_even_month, a.months),
            "extra funding needed to stay cash-positive": money(s.funding_gap),
            "customers at end of horizon": f"{s.ending_customers:,.0f}",
            "annual recurring revenue at end of horizon": money(s.ending_arr),
        },
        "VentureLens score": {"overall": f"{card.overall:.1f} / 10", "verdict": card.verdict},
    }


def run_ai(
    llm: SupportsLLM,
    idea: IdeaInput,
    a: Assumptions,
    m: MarketInputs,
    c: Computed,
    on_step: Callable[[str], object] | None = None,
) -> dict:
    """Two model calls: structured assessment, then the memo. Returns a JSON-safe dict."""
    step = on_step or (lambda _msg: None)
    step("Analyst agent: sizing up the problem, competition, moats and risks…")
    assessment = assess_idea(llm, idea)
    card = build_scorecard(c.market, c.unit, c.summary, assessment, a.months)
    step("Memo agent: writing the investment memo from the computed figures…")
    memo = write_memo(llm, idea, assessment, memo_facts(a, c, card))
    return {
        "fingerprint": fingerprint(idea, a, m),
        "idea_fingerprint": idea_fingerprint(idea),
        "assessment": assessment.model_dump(),
        "memo": memo,
        "model": getattr(llm, "last_model", None),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
