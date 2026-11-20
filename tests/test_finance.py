import math

import pytest

from venturelens.finance import (
    MAX_LIFETIME_MONTHS,
    Assumptions,
    MarketInputs,
    market_size,
    project,
    sensitivity,
    summarize,
    unit_economics,
)


def test_unit_economics_textbook_case():
    a = Assumptions(arpu_monthly=50, gross_margin=0.8, cac=200, monthly_churn=0.05)
    u = unit_economics(a)
    assert u.contribution_monthly == pytest.approx(40)
    assert u.lifetime_months == pytest.approx(20)
    assert u.ltv == pytest.approx(800)
    assert u.ltv_to_cac == pytest.approx(4)
    assert u.payback_months == pytest.approx(5)


def test_zero_churn_caps_lifetime():
    u = unit_economics(Assumptions(arpu_monthly=10, gross_margin=1.0, cac=100, monthly_churn=0))
    assert u.lifetime_months == MAX_LIFETIME_MONTHS
    assert u.ltv == pytest.approx(10 * MAX_LIFETIME_MONTHS)


def test_free_acquisition_and_negative_margin_edge_cases():
    assert math.isinf(unit_economics(Assumptions(cac=0)).ltv_to_cac)
    assert unit_economics(Assumptions(cac=0)).payback_months == 0
    assert math.isinf(unit_economics(Assumptions(gross_margin=0)).payback_months)


def test_market_size_bottom_up():
    a = Assumptions(arpu_monthly=10)
    ms = market_size(MarketInputs(potential_customers=1000, serviceable_share=0.5, obtainable_share=0.1), a)
    assert ms.tam == pytest.approx(120_000)
    assert ms.sam == pytest.approx(60_000)
    assert ms.som == pytest.approx(6_000)


def test_projection_cash_identity_and_length():
    a = Assumptions(months=24)
    df = project(a)
    assert len(df) == 24
    assert df["cash"].iloc[-1] == pytest.approx(a.starting_cash + df["net_cash_flow"].sum())
    assert (df["customers"] >= 0).all()


def test_customers_follow_churn_then_additions():
    a = Assumptions(starting_customers=100, monthly_churn=0.1, new_customers_month1=10, new_customer_growth=0, months=2)
    df = project(a)
    assert df.loc[0, "customers"] == pytest.approx(100 - 10 + 10)
    assert df.loc[1, "customers"] == pytest.approx(100 - 10 + 10)


def test_break_even_immediate_when_no_costs():
    a = Assumptions(starting_customers=10, cac=0, fixed_costs_monthly=0, months=12)
    assert summarize(project(a), a).break_even_month == 1


def test_break_even_never_and_runway():
    a = Assumptions(arpu_monthly=1, fixed_costs_monthly=50_000, starting_cash=100_000, months=12)
    summary = summarize(project(a), a)
    assert summary.break_even_month is None
    assert summary.runway_months is not None and summary.runway_months < 12
    assert summary.funding_gap > 0


def test_break_even_is_sustained_not_first_positive_month():
    a = Assumptions()
    df = project(a)
    summary = summarize(df, a)
    if summary.break_even_month is not None:
        assert (df.loc[df["month"] >= summary.break_even_month, "net_cash_flow"] >= 0).all()


def test_sensitivity_sorted_and_margin_capped():
    a = Assumptions(gross_margin=0.95)
    sens = sensitivity(a)
    assert list(sens["swing"]) == sorted(sens["swing"], reverse=True)
    assert set(sens["field"]) == {
        "arpu_monthly",
        "gross_margin",
        "cac",
        "monthly_churn",
        "new_customer_growth",
        "fixed_costs_monthly",
    }
    price = sens.set_index("field").loc["arpu_monthly"]
    assert price["impact_high"] > 0 > price["impact_low"]
