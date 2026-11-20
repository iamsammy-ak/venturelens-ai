import math

import pytest

from venturelens.finance import Assumptions, MarketInputs, market_size, project, summarize, unit_economics
from venturelens.schemas import DimensionScore, IdeaAssessment
from venturelens.scoring import (
    WEIGHTS,
    build_scorecard,
    score_capital_efficiency,
    score_market_size,
    score_unit_economics,
    verdict_for,
)


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_scores_are_monotonic_and_bounded():
    assert score_market_size(0) == 0
    assert score_market_size(1e5) < score_market_size(1e6) < score_market_size(1e7) <= 10
    assert score_unit_economics(0.5) < score_unit_economics(3) < score_unit_economics(5) == 10
    assert score_unit_economics(math.inf) == 10
    assert score_capital_efficiency(6) > score_capital_efficiency(24) > score_capital_efficiency(None)


def _inputs():
    a = Assumptions()
    df = project(a)
    return market_size(MarketInputs(), a), unit_economics(a), summarize(df, a)


def test_partial_scorecard_without_ai():
    card = build_scorecard(*_inputs())
    assert not card.complete
    assert set(card.dimensions) == {"market_size", "unit_economics", "capital_efficiency"}
    assert 0 <= card.overall <= 10


def test_full_scorecard_uses_ai_dimensions():
    perfect = DimensionScore(score=10, rationale="x")
    assessment = IdeaAssessment(
        one_liner="x",
        problem_urgency=perfect,
        competitive_position=perfect,
        defensibility=perfect,
        execution_feasibility=perfect,
    )
    partial = build_scorecard(*_inputs())
    full = build_scorecard(*_inputs(), assessment=assessment)
    assert full.complete and len(full.dimensions) == 7
    assert full.overall > partial.overall


@pytest.mark.parametrize(("score", "word"), [(8, "Strong"), (6.5, "Promising"), (5, "Needs work"), (2, "Weak")])
def test_verdict_bands(score, word):
    assert verdict_for(score).startswith(word)
