"""Plotly figures used by the app. Colours follow the VentureLens violet palette."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .finance import MarketSize, ProjectionSummary, UnitEconomics
from .formatting import money
from .scoring import LABELS, Scorecard

ACCENT = "#7C3AED"
ACCENT_SOFT = "#C4B5FD"
ACCENT_DARK = "#4C1D95"
GOOD = "#059669"
BAD = "#DC2626"
MUTED = "#94A3B8"
FONT = "Inter, 'Segoe UI', system-ui, sans-serif"


def _style(fig: go.Figure, height: int = 340, title: str | None = None) -> go.Figure:
    fig.update_layout(
        height=height,
        title=dict(text=title, x=0, font=dict(size=15)) if title else None,
        margin=dict(l=8, r=8, t=48 if title else 16, b=8),
        font=dict(family=FONT, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(font_family=FONT),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.25)", zeroline=False)
    return fig


def score_gauge(card: Scorecard) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=card.overall,
            number=dict(suffix=" / 10", valueformat=".1f", font=dict(size=40, color=ACCENT_DARK)),
            gauge=dict(
                axis=dict(range=[0, 10], tickwidth=1),
                bar=dict(color=ACCENT, thickness=0.28),
                steps=[
                    dict(range=[0, 4.5], color="rgba(220,38,38,0.12)"),
                    dict(range=[4.5, 6], color="rgba(234,179,8,0.14)"),
                    dict(range=[6, 7.5], color="rgba(124,58,237,0.12)"),
                    dict(range=[7.5, 10], color="rgba(5,150,105,0.16)"),
                ],
            ),
        )
    )
    return _style(fig, height=280)


def score_radar(card: Scorecard) -> go.Figure:
    keys = list(card.dimensions)
    labels = [LABELS[k] for k in keys] + [LABELS[keys[0]]]
    values = [card.dimensions[k] for k in keys] + [card.dimensions[keys[0]]]
    fig = go.Figure(
        go.Scatterpolar(
            r=values,
            theta=labels,
            fill="toself",
            line=dict(color=ACCENT, width=2),
            fillcolor="rgba(124,58,237,0.18)",
            hovertemplate="%{theta}: %{r:.1f}<extra></extra>",
        )
    )
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 10], showline=False, gridcolor="rgba(148,163,184,0.3)")))
    _style(fig, height=340)
    fig.update_layout(margin=dict(l=70, r=70, t=30, b=40))
    return fig


def ltv_vs_cac(unit: UnitEconomics, cac: float) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=["Customer acquisition cost", "Customer lifetime value"],
            y=[cac, unit.ltv],
            marker_color=[MUTED, ACCENT],
            text=[money(cac), money(unit.ltv)],
            textposition="outside",
            hovertemplate="%{x}: %{text}<extra></extra>",
        )
    )
    fig.update_yaxes(title="€ per customer")
    return _style(fig, height=320, title="What a customer costs vs what they are worth")


def market_funnel(market: MarketSize) -> go.Figure:
    fig = go.Figure(
        go.Funnel(
            y=["TAM · everyone with the problem", "SAM · reachable with this offer", "SOM · realistically winnable"],
            x=[market.tam, market.sam, market.som],
            text=[money(market.tam), money(market.sam), money(market.som)],
            textinfo="text",
            marker=dict(color=[ACCENT_SOFT, "#A78BFA", ACCENT]),
            hovertemplate="%{y}: %{text} a year<extra></extra>",
        )
    )
    return _style(fig, height=320, title="Annual revenue opportunity")


def customers_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(
        x=df["month"],
        y=df["customers"],
        mode="lines",
        line=dict(color=ACCENT, width=3),
        fill="tozeroy",
        fillcolor="rgba(124,58,237,0.12)",
        name="Active customers",
        hovertemplate="Month %{x}: %{y:,.0f} customers<extra></extra>",
    )
    fig.update_xaxes(title="Month")
    return _style(fig, title="Active customers")


def revenue_costs_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=df["month"], y=df["fixed_costs"], name="Fixed costs", marker_color="#CBD5E1")
    fig.add_bar(x=df["month"], y=df["marketing"], name="Acquisition spend", marker_color=ACCENT_SOFT)
    fig.add_scatter(
        x=df["month"], y=df["gross_profit"], name="Gross profit", mode="lines", line=dict(color=ACCENT, width=3)
    )
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title="Month")
    fig.update_yaxes(title="€ per month")
    return _style(fig, title="Gross profit vs costs")


def cash_chart(df: pd.DataFrame, summary: ProjectionSummary) -> go.Figure:
    colors = [GOOD if v >= 0 else BAD for v in df["cash"]]
    fig = go.Figure()
    fig.add_scatter(
        x=df["month"],
        y=df["cash"],
        mode="lines+markers",
        marker=dict(size=5, color=colors),
        line=dict(color=ACCENT_DARK, width=2),
        name="Cash balance",
        hovertemplate="Month %{x}: €%{y:,.0f}<extra></extra>",
    )
    fig.add_hline(y=0, line=dict(color=BAD, width=1, dash="dot"))
    if summary.break_even_month is not None:
        fig.add_vline(
            x=summary.break_even_month,
            line=dict(color=GOOD, width=1, dash="dash"),
            annotation_text="Break-even",
            annotation_position="top left",
        )
    fig.update_xaxes(title="Month")
    fig.update_yaxes(title="€")
    return _style(fig, title="Cash balance")


def tornado(sens: pd.DataFrame, horizon: int) -> go.Figure:
    data = sens.iloc[::-1]
    fig = go.Figure()
    fig.add_bar(
        y=data["driver"],
        x=data["impact_low"],
        orientation="h",
        name="Driver −20%",
        marker_color=MUTED,
        hovertemplate="%{y} −20%%: €%{x:,.0f}<extra></extra>",
    )
    fig.add_bar(
        y=data["driver"],
        x=data["impact_high"],
        orientation="h",
        name="Driver +20%",
        marker_color=ACCENT,
        hovertemplate="%{y} +20%%: €%{x:,.0f}<extra></extra>",
    )
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(title=f"Change in cash at month {horizon} (€)", zeroline=True, zerolinecolor=MUTED)
    return _style(fig, height=360, title="Which assumption moves the outcome most?")
