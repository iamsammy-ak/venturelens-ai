"""Downloadable Markdown report: computed figures, scorecard and (when available) AI analysis."""

from __future__ import annotations

from datetime import date

from .finance import Assumptions, MarketInputs
from .formatting import money, month_label, months, pct, ratio
from .pipeline import Computed
from .schemas import IdeaAssessment, IdeaInput
from .scoring import LABELS, Scorecard


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) or "- —"


def build_report(
    idea: IdeaInput,
    a: Assumptions,
    m: MarketInputs,
    c: Computed,
    card: Scorecard,
    assessment: IdeaAssessment | None,
    memo: str | None,
    model: str | None,
) -> str:
    s = c.summary
    lines = [
        f"# {idea.name}: VentureLens report",
        "",
        f"_Generated {date.today().isoformat()}"
        + (f" · AI analysis by `{model}`" if model else " · numbers only, no AI analysis")
        + "_",
        "",
        f"> {idea.description}",
        "",
        f"**VentureLens score: {card.overall:.1f} / 10** · {card.verdict}"
        + ("" if card.complete else " _(partial: computed dimensions only)_"),
        "",
        "| Dimension | Score | Source |",
        "|---|---:|---|",
    ]
    for key, value in card.dimensions.items():
        lines.append(f"| {LABELS[key]} | {value:.1f} | {card.source(key)} |")

    lines += [
        "",
        "## Key figures",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Customer lifetime value (LTV) | {money(c.unit.ltv)} |",
        f"| LTV : CAC | {ratio(c.unit.ltv_to_cac)} |",
        f"| CAC payback | {months(c.unit.payback_months)} |",
        f"| TAM / SAM / SOM | {money(c.market.tam)} / {money(c.market.sam)} / {money(c.market.som)} |",
        f"| Sustained break-even | {month_label(s.break_even_month, a.months)} |",
        f"| Extra funding needed | {money(s.funding_gap)} |",
        f"| ARR at month {a.months} | {money(s.ending_arr)} |",
        "",
    ]

    if memo:
        lines += ["## Investment memo", "", memo.strip(), ""]

    if assessment is not None:
        sw = assessment.swot
        lines += [
            "## SWOT",
            "",
            "**Strengths**",
            _bullets(sw.strengths),
            "",
            "**Weaknesses**",
            _bullets(sw.weaknesses),
            "",
            "**Opportunities**",
            _bullets(sw.opportunities),
            "",
            "**Threats**",
            _bullets(sw.threats),
            "",
            "## Risks",
            "",
            "| Risk | Severity | Mitigation |",
            "|---|---|---|",
        ]
        lines += [f"| {r.risk} | {r.severity} | {r.mitigation} |" for r in assessment.risks]
        lines += [
            "",
            "## Competitors and substitutes (model-generated: verify before relying on them)",
            "",
        ]
        lines += [f"- **{comp.name}** ({comp.kind}): {comp.note}" for comp in assessment.competitors]
        lines += [
            "",
            "## Questions an investor will ask",
            "",
            _bullets(assessment.investor_questions),
            "",
            "## Cheap validation experiments",
            "",
            _bullets(assessment.validation_experiments),
            "",
        ]

    lines += [
        "## Assumptions",
        "",
        f"- Revenue per customer per month: {money(a.arpu_monthly)}; gross margin {pct(a.gross_margin, 0)}",
        f"- CAC {money(a.cac)}; monthly churn {pct(a.monthly_churn)}",
        f"- New customers in month 1: {a.new_customers_month1:,.0f}, growing {pct(a.new_customer_growth)} a month",
        f"- Fixed costs {money(a.fixed_costs_monthly)} a month, growing {pct(a.fixed_cost_growth)} a month",
        f"- Starting cash {money(a.starting_cash)}; horizon {a.months} months",
        f"- Market: {m.potential_customers:,.0f} potential customers, {pct(m.serviceable_share, 0)} serviceable, "
        f"{pct(m.obtainable_share)} obtainable",
        "",
        "---",
        "_VentureLens AI is a decision-support tool, not investment advice. Figures depend entirely on the "
        "assumptions above; AI-generated content can be wrong and should be verified._",
    ]
    return "\n".join(lines)
