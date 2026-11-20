"""Deterministic startup finance: unit economics, bottom-up market sizing, a monthly
cash-flow projection and a one-at-a-time sensitivity analysis.

Every number the app reports comes from here, not from the language model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import pandas as pd

MAX_LIFETIME_MONTHS = 60  # cap on customer lifetime so LTV stays finite at very low churn


@dataclass(frozen=True)
class Assumptions:
    arpu_monthly: float = 49.0  # net revenue per customer per month (€)
    gross_margin: float = 0.75  # share of revenue left after direct costs (0-1)
    cac: float = 300.0  # cost to acquire one customer (€)
    monthly_churn: float = 0.03  # share of customers lost each month (0-1)
    starting_customers: float = 0.0
    new_customers_month1: float = 20.0
    new_customer_growth: float = 0.08  # monthly growth of new-customer additions
    fixed_costs_monthly: float = 15_000.0  # salaries, rent, tools (€)
    fixed_cost_growth: float = 0.02  # monthly growth of fixed costs
    starting_cash: float = 250_000.0
    months: int = 36


@dataclass(frozen=True)
class MarketInputs:
    potential_customers: float = 200_000  # every customer who has the problem
    serviceable_share: float = 0.30  # share you can reach with this product and channel
    obtainable_share: float = 0.05  # share of the serviceable market you can realistically win


@dataclass(frozen=True)
class UnitEconomics:
    contribution_monthly: float
    lifetime_months: float
    ltv: float
    ltv_to_cac: float
    payback_months: float  # math.inf when the customer never pays back


@dataclass(frozen=True)
class MarketSize:
    tam: float
    sam: float
    som: float


@dataclass(frozen=True)
class ProjectionSummary:
    break_even_month: int | None  # first month from which net cash flow stays non-negative
    min_cash: float
    min_cash_month: int
    funding_gap: float  # extra cash needed so the balance never goes negative
    runway_months: int | None  # months before cash runs out; None = lasts the whole horizon
    ending_customers: float
    ending_arr: float
    total_revenue: float


def unit_economics(a: Assumptions) -> UnitEconomics:
    contribution = a.arpu_monthly * a.gross_margin
    if a.monthly_churn <= 0:
        lifetime = float(MAX_LIFETIME_MONTHS)
    else:
        lifetime = min(1.0 / a.monthly_churn, float(MAX_LIFETIME_MONTHS))
    ltv = contribution * lifetime
    ltv_to_cac = ltv / a.cac if a.cac > 0 else math.inf
    if a.cac <= 0:
        payback = 0.0
    elif contribution > 0:
        payback = a.cac / contribution
    else:
        payback = math.inf
    return UnitEconomics(contribution, lifetime, ltv, ltv_to_cac, payback)


def market_size(m: MarketInputs, a: Assumptions) -> MarketSize:
    """Bottom-up sizing: customers × annual revenue per customer, narrowed twice."""
    tam = m.potential_customers * a.arpu_monthly * 12
    sam = tam * m.serviceable_share
    som = sam * m.obtainable_share
    return MarketSize(tam, sam, som)


def project(a: Assumptions) -> pd.DataFrame:
    """Month-by-month projection. Churn applies to customers at the start of each month."""
    rows = []
    customers = float(a.starting_customers)
    cash = float(a.starting_cash)
    for month in range(1, a.months + 1):
        new = a.new_customers_month1 * (1 + a.new_customer_growth) ** (month - 1)
        churned = customers * a.monthly_churn
        customers = customers - churned + new
        revenue = customers * a.arpu_monthly
        gross_profit = revenue * a.gross_margin
        marketing = new * a.cac
        fixed = a.fixed_costs_monthly * (1 + a.fixed_cost_growth) ** (month - 1)
        net = gross_profit - marketing - fixed
        cash += net
        rows.append(
            {
                "month": month,
                "new_customers": new,
                "churned": churned,
                "customers": customers,
                "revenue": revenue,
                "gross_profit": gross_profit,
                "marketing": marketing,
                "fixed_costs": fixed,
                "net_cash_flow": net,
                "cash": cash,
            }
        )
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame, a: Assumptions) -> ProjectionSummary:
    negative_months = df.loc[df["net_cash_flow"] < 0, "month"]
    if negative_months.empty:
        break_even: int | None = 1
    elif int(negative_months.iloc[-1]) >= a.months:
        break_even = None
    else:
        break_even = int(negative_months.iloc[-1]) + 1

    min_idx = df["cash"].idxmin()
    min_cash = float(df.loc[min_idx, "cash"])
    below_zero = df.loc[df["cash"] < 0, "month"]
    runway = int(below_zero.iloc[0]) - 1 if not below_zero.empty else None

    last = df.iloc[-1]
    return ProjectionSummary(
        break_even_month=break_even,
        min_cash=min_cash,
        min_cash_month=int(df.loc[min_idx, "month"]),
        funding_gap=max(0.0, -min_cash),
        runway_months=runway,
        ending_customers=float(last["customers"]),
        ending_arr=float(last["revenue"]) * 12,
        total_revenue=float(df["revenue"].sum()),
    )


SENSITIVITY_DRIVERS: dict[str, str] = {
    "arpu_monthly": "Price per customer",
    "gross_margin": "Gross margin",
    "cac": "Acquisition cost (CAC)",
    "monthly_churn": "Monthly churn",
    "new_customer_growth": "New-customer growth",
    "fixed_costs_monthly": "Fixed costs",
}


def sensitivity(a: Assumptions, delta: float = 0.2) -> pd.DataFrame:
    """Change each driver by ±delta and report the effect on cash at the end of the horizon."""
    base = float(project(a)["cash"].iloc[-1])
    rows = []
    for field, label in SENSITIVITY_DRIVERS.items():
        value = getattr(a, field)
        low_value, high_value = value * (1 - delta), value * (1 + delta)
        if field == "gross_margin":
            high_value = min(high_value, 1.0)
        low_cash = float(project(replace(a, **{field: low_value}))["cash"].iloc[-1])
        high_cash = float(project(replace(a, **{field: high_value}))["cash"].iloc[-1])
        rows.append(
            {
                "driver": label,
                "field": field,
                "impact_low": low_cash - base,
                "impact_high": high_cash - base,
            }
        )
    out = pd.DataFrame(rows)
    out["swing"] = (out["impact_high"] - out["impact_low"]).abs()
    return out.sort_values("swing", ascending=False, ignore_index=True)
