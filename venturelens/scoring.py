"""Weighted 0-10 scorecard. Three dimensions are computed from the numbers; four come from
the AI analyst. Without an AI assessment the score is computed on the numeric dimensions only
and flagged as partial."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .finance import MarketSize, ProjectionSummary, UnitEconomics
from .schemas import IdeaAssessment

WEIGHTS: dict[str, float] = {
    "market_size": 0.15,
    "unit_economics": 0.20,
    "capital_efficiency": 0.15,
    "problem_urgency": 0.15,
    "competitive_position": 0.10,
    "defensibility": 0.15,
    "execution_feasibility": 0.10,
}

LABELS: dict[str, str] = {
    "market_size": "Market size",
    "unit_economics": "Unit economics",
    "capital_efficiency": "Capital efficiency",
    "problem_urgency": "Problem urgency",
    "competitive_position": "Competitive position",
    "defensibility": "Defensibility",
    "execution_feasibility": "Execution feasibility",
}

COMPUTED = ("market_size", "unit_economics", "capital_efficiency")
AI_JUDGED = ("problem_urgency", "competitive_position", "defensibility", "execution_feasibility")


def score_market_size(som: float) -> float:
    """€100k obtainable market scores 2, €1M scores 5, €10M scores 8, €100M+ scores 10."""
    if som <= 0:
        return 0.0
    return float(np.interp(math.log10(som), [4, 5, 6, 7, 8], [0, 2, 5, 8, 10]))


def score_unit_economics(ltv_to_cac: float) -> float:
    """LTV:CAC of 1 scores 2.5, 3 (the usual benchmark) scores 7.5, 5+ scores 10."""
    if math.isinf(ltv_to_cac):
        return 10.0
    return float(np.interp(ltv_to_cac, [0, 1, 3, 5], [0, 2.5, 7.5, 10]))


def score_capital_efficiency(break_even_month: int | None, horizon: int = 36) -> float:
    """Break-even within 6 months scores 10, 12 → 9, 24 → 6, 36 → 3; never → 1."""
    month = break_even_month if break_even_month is not None else horizon + 12
    return float(np.interp(month, [6, 12, 24, 36, 48], [10, 9, 6, 3, 1]))


@dataclass(frozen=True)
class Scorecard:
    dimensions: dict[str, float]
    overall: float
    complete: bool
    verdict: str

    def source(self, key: str) -> str:
        return "Computed" if key in COMPUTED else "AI analyst"


def verdict_for(score: float) -> str:
    if score >= 7.5:
        return "Strong: worth pursuing"
    if score >= 6.0:
        return "Promising: validate the key assumptions"
    if score >= 4.5:
        return "Needs work before it is investable"
    return "Weak as currently framed"


def build_scorecard(
    market: MarketSize,
    unit: UnitEconomics,
    summary: ProjectionSummary,
    assessment: IdeaAssessment | None = None,
    horizon: int = 36,
) -> Scorecard:
    dims = {
        "market_size": score_market_size(market.som),
        "unit_economics": score_unit_economics(unit.ltv_to_cac),
        "capital_efficiency": score_capital_efficiency(summary.break_even_month, horizon),
    }
    if assessment is not None:
        for key in AI_JUDGED:
            dims[key] = getattr(assessment, key).score
    total_weight = sum(WEIGHTS[k] for k in dims)
    overall = sum(WEIGHTS[k] * v for k, v in dims.items()) / total_weight
    return Scorecard(dims, round(overall, 2), assessment is not None, verdict_for(overall))
