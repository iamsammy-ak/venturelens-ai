"""VentureLens AI: evaluate a startup idea with computed unit economics and an AI analyst."""

from __future__ import annotations

import re

import streamlit as st

from venturelens import charts
from venturelens.config import load_settings
from venturelens.demo import load_samples, load_saved_analysis, sample_inputs
from venturelens.finance import Assumptions, MarketInputs
from venturelens.formatting import money, month_label, months, pct, ratio
from venturelens.llm import LLMClient, LLMError
from venturelens.pipeline import compute, fingerprint, idea_fingerprint, run_ai
from venturelens.report import build_report
from venturelens.schemas import IdeaAssessment, IdeaInput
from venturelens.scoring import AI_JUDGED, LABELS, build_scorecard
from venturelens.ui import card, hero, inject_css, pill, score_bar, severity, table

st.set_page_config(page_title="VentureLens AI", page_icon="🔭", layout="wide")
inject_css()

BUSINESS_MODELS = [
    "Subscription (SaaS)",
    "Marketplace (take rate)",
    "E-commerce / D2C",
    "Usage-based",
    "Services / agency",
    "Hardware + subscription",
]
SAMPLES = load_samples()
SAMPLE_NAMES = [s["idea"]["name"] for s in SAMPLES]
BLANK = "Blank idea"
ss = st.session_state


# ----------------------------------------------------------------------------- state
def _state_from(idea: IdeaInput, a: Assumptions, m: MarketInputs) -> dict:
    return {
        "idea_name": idea.name,
        "idea_description": idea.description,
        "idea_target": idea.target_customer,
        "idea_geo": idea.geography,
        "idea_model": idea.business_model,
        "arpu": float(a.arpu_monthly),
        "gm_pct": round(a.gross_margin * 100, 4),
        "cac": float(a.cac),
        "churn_pct": round(a.monthly_churn * 100, 4),
        "start_customers": int(a.starting_customers),
        "new_m1": int(a.new_customers_month1),
        "new_growth_pct": round(a.new_customer_growth * 100, 4),
        "fixed": float(a.fixed_costs_monthly),
        "fixed_growth_pct": round(a.fixed_cost_growth * 100, 4),
        "cash": float(a.starting_cash),
        "horizon": int(a.months),
        "potential": int(m.potential_customers),
        "sam_pct": round(m.serviceable_share * 100, 4),
        "som_pct": round(m.obtainable_share * 100, 4),
    }


def _load_choice() -> None:
    choice = ss["sample_choice"]
    if choice == BLANK:
        idea = IdeaInput(name="", description="", business_model=BUSINESS_MODELS[0])
        ss.update(_state_from(idea, Assumptions(), MarketInputs()))
    else:
        ss.update(_state_from(*sample_inputs(SAMPLES[SAMPLE_NAMES.index(choice)])))


if "sample_choice" not in ss:
    ss["sample_choice"] = SAMPLE_NAMES[0]
    _load_choice()


def current_inputs() -> tuple[IdeaInput, Assumptions, MarketInputs]:
    idea = IdeaInput(
        name=ss.idea_name.strip() or "Untitled idea",
        description=ss.idea_description.strip(),
        target_customer=ss.idea_target.strip(),
        geography=ss.idea_geo.strip(),
        business_model=ss.idea_model,
    )
    a = Assumptions(
        arpu_monthly=float(ss.arpu),
        gross_margin=ss.gm_pct / 100,
        cac=float(ss.cac),
        monthly_churn=ss.churn_pct / 100,
        starting_customers=float(ss.start_customers),
        new_customers_month1=float(ss.new_m1),
        new_customer_growth=ss.new_growth_pct / 100,
        fixed_costs_monthly=float(ss.fixed),
        fixed_cost_growth=ss.fixed_growth_pct / 100,
        starting_cash=float(ss.cash),
        months=int(ss.horizon),
    )
    m = MarketInputs(
        potential_customers=float(ss.potential),
        serviceable_share=ss.sam_pct / 100,
        obtainable_share=ss.som_pct / 100,
    )
    return idea, a, m


# --------------------------------------------------------------------------- sidebar
settings = load_settings()
with st.sidebar:
    st.markdown("## 🔭 VentureLens AI")
    if settings.live:
        fallbacks = len(settings.models) - 1
        st.success(f"**Live AI** via OpenRouter\n\n`{settings.models[0]}`\n\n+{fallbacks} fallback models")
    else:
        st.info(
            "**Demo mode**: every figure is computed live; saved AI analyses are included for some sample ideas.\n\n"
            "Add `OPENROUTER_API_KEY` (see README) to run the AI analyst on any idea."
        )
    st.selectbox("Load an idea", SAMPLE_NAMES + [BLANK], key="sample_choice", on_change=_load_choice)

    st.markdown("### Assumptions")
    st.caption("Sample figures are illustrative. Replace them with your own evidence.")
    with st.expander("Revenue and unit economics", expanded=True):
        st.number_input("Revenue per customer / month (€)", min_value=0.0, step=5.0, key="arpu")
        st.slider("Gross margin (%)", 0.0, 100.0, step=1.0, key="gm_pct")
        st.number_input("Customer acquisition cost (€)", min_value=0.0, step=10.0, key="cac")
        st.number_input("Monthly churn (%)", min_value=0.0, max_value=100.0, step=0.5, key="churn_pct")
    with st.expander("Growth"):
        st.number_input("Customers at launch", min_value=0, step=1, key="start_customers")
        st.number_input("New customers in month 1", min_value=0, step=1, key="new_m1")
        st.number_input("Monthly growth of new customers (%)", min_value=-50.0, max_value=100.0, step=0.5,
                        key="new_growth_pct")
    with st.expander("Costs and funding"):
        st.number_input("Fixed costs / month (€)", min_value=0.0, step=1000.0, key="fixed")
        st.number_input("Fixed-cost growth / month (%)", min_value=-10.0, max_value=50.0, step=0.5,
                        key="fixed_growth_pct")
        st.number_input("Starting cash (€)", min_value=0.0, step=10000.0, key="cash")
        st.select_slider("Projection horizon (months)", options=[24, 36, 48, 60], key="horizon")
    with st.expander("Market size"):
        st.number_input("Potential customers with the problem", min_value=0, step=1000, key="potential")
        st.slider("Serviceable share (%)", 0.0, 100.0, step=1.0, key="sam_pct")
        st.slider("Winnable share of serviceable market (%)", 0.0, 100.0, step=0.5, key="som_pct")

# ------------------------------------------------------------------------------ main
hero(
    "VentureLens AI",
    "Evaluate a startup idea the way an investment committee would: computed unit economics, "
    "bottom-up market sizing and cash runway, plus an AI analyst's assessment and memo.",
    ["Unit economics", "TAM · SAM · SOM", "Cash-flow projection", "Sensitivity analysis", "AI investment memo"],
)

with st.expander("💡 The idea", expanded=True):
    st.text_input("Name", key="idea_name", placeholder="e.g. StudyNest")
    st.text_area("What does it do, for whom, and why now?", key="idea_description", height=100)
    col1, col2, col3 = st.columns(3)
    col1.text_input("Target customer", key="idea_target")
    col2.text_input("Geography", key="idea_geo")
    col3.selectbox("Business model", BUSINESS_MODELS, key="idea_model")

idea, a, m = current_inputs()
c = compute(a, m)
s = c.summary
fp, ifp = fingerprint(idea, a, m), idea_fingerprint(idea)

# ------------------------------------------------------------------------ AI analysis
run_col, note_col = st.columns([1, 2.6], vertical_alignment="center")
can_run = settings.live and bool(idea.description)
clicked = run_col.button("✨ Run AI analysis", type="primary", disabled=not can_run, width="stretch")
if clicked:
    with st.status("Running the AI analysts…", expanded=True) as status:
        try:
            llm = LLMClient(settings, app_name="VentureLens AI")
            ss["analysis"] = run_ai(llm, idea, a, m, c, on_step=status.write)
            status.update(label=f"Analysis complete · {ss['analysis']['model']}", state="complete", expanded=False)
        except LLMError as exc:
            status.update(label="The AI analysis failed", state="error")
            st.error(str(exc))

analysis, freshness = None, None
current = ss.get("analysis")
if current and current["fingerprint"] == fp:
    analysis, freshness = current, "fresh"
elif (saved := load_saved_analysis(fp)) is not None:
    analysis, freshness = saved, "saved"
elif current and current["idea_fingerprint"] == ifp:
    analysis, freshness = current, "numbers_changed"

assessment = IdeaAssessment.model_validate(analysis["assessment"]) if analysis else None
scorecard = build_scorecard(c.market, c.unit, s, assessment, a.months)

if freshness == "saved":
    note_col.caption(
        f"Showing the saved AI analysis for this sample (`{analysis['model']}`, "
        f"{analysis['generated_at'][:10]}). No model calls used."
    )
elif freshness == "fresh":
    note_col.caption(f"AI analysis by `{analysis['model']}`. Repeat runs are served from the cache.")
elif freshness == "numbers_changed":
    note_col.caption("⚠️ Assumptions changed after the AI analysis: scores still apply, re-run to refresh the memo.")
elif settings.live:
    note_col.caption("Two calls to free OpenRouter models, usually 30-90 seconds. Results are cached.")
else:
    note_col.caption("Demo mode: the AI analysis runs once an OpenRouter key is configured. All figures below are "
                     "computed.")

NO_KEY_HINT = (
    "The AI analysis runs once an OpenRouter key is configured: add `OPENROUTER_API_KEY` "
    "(see README → Quick start), then click **Run AI analysis**."
)

# ------------------------------------------------------------------------- headline
kpis = st.columns(6)
kpis[0].metric(
    "Score" + ("" if scorecard.complete else " (partial)"),
    f"{scorecard.overall:.1f} / 10",
    help="Weighted VentureLens score across seven dimensions. Partial = computed dimensions only (no AI yet).",
)
kpis[1].metric("LTV : CAC", ratio(c.unit.ltv_to_cac), help="Lifetime gross profit per customer ÷ acquisition cost.")
payback = c.unit.payback_months
kpis[2].metric("CAC payback", "Never" if payback == float("inf") else f"{payback:.1f} mo")
kpis[3].metric(
    "Break-even",
    f"Month {s.break_even_month}" if s.break_even_month else f"> M{a.months}",
    help="First month from which monthly net cash flow stays non-negative.",
)
kpis[4].metric("Funding gap", money(s.funding_gap), help="Extra cash required so the balance never goes negative.")
kpis[5].metric("SOM / year", money(c.market.som), help="Obtainable market: annual revenue you can realistically win.")
pill(scorecard.verdict)
st.write("")

tabs = st.tabs(
    ["📊 Scorecard", "💶 Unit economics", "🌍 Market", "📈 Projection", "🎯 Sensitivity", "🧠 AI assessment",
     "📝 Memo & report"]
)

# ------------------------------------------------------------------------- scorecard
with tabs[0]:
    left, right = st.columns([1, 1.25])
    left.plotly_chart(charts.score_gauge(scorecard), width="stretch")
    right.plotly_chart(charts.score_radar(scorecard), width="stretch")
    computed_reason = {
        "market_size": f"Winnable market of {money(c.market.som)} a year (log scale: €1M → 5, €10M → 8).",
        "unit_economics": f"LTV:CAC of {ratio(c.unit.ltv_to_cac)} against the usual 3× benchmark.",
        "capital_efficiency": f"Sustained break-even: {month_label(s.break_even_month, a.months)}.",
    }
    rows = []
    for key, value in scorecard.dimensions.items():
        reason = computed_reason.get(key) or getattr(assessment, key).rationale
        rows.append([LABELS[key], score_bar(value), scorecard.source(key), reason])
    if not scorecard.complete:
        for key in AI_JUDGED:
            rows.append([LABELS[key], score_bar(None), "AI analyst", "Scored when the AI analysis runs."])
    table(["Dimension", "Score", "Source", "Why"], rows, html_cols=(1,))

# -------------------------------------------------------------------- unit economics
with tabs[1]:
    u = c.unit
    cols = st.columns(4)
    cols[0].metric("Gross profit / customer / month", money(u.contribution_monthly))
    cols[1].metric("Expected customer lifetime", months(u.lifetime_months))
    cols[2].metric("Lifetime value (LTV)", money(u.ltv))
    cols[3].metric("CAC payback", months(u.payback_months))
    left, right = st.columns([1.3, 1])
    left.plotly_chart(charts.ltv_vs_cac(u, a.cac), width="stretch")
    right.markdown(
        f"""
**How it is calculated**

- Gross profit per month = {money(a.arpu_monthly)} × {pct(a.gross_margin, 0)} = **{money(u.contribution_monthly)}**
- Lifetime = 1 ÷ churn = 1 ÷ {pct(a.monthly_churn)} = **{months(u.lifetime_months)}** (capped at 60)
- LTV = gross profit × lifetime = **{money(u.ltv)}**
- LTV : CAC = {money(u.ltv)} ÷ {money(a.cac)} = **{ratio(u.ltv_to_cac)}**
- Payback = CAC ÷ monthly gross profit = **{months(u.payback_months)}**

A ratio above **3×** and payback under **12 months** are the usual early-stage benchmarks.
"""
    )

# ---------------------------------------------------------------------------- market
with tabs[2]:
    left, right = st.columns([1.3, 1])
    left.plotly_chart(charts.market_funnel(c.market), width="stretch")
    right.markdown(
        f"""
**Bottom-up sizing**

- **TAM** = {m.potential_customers:,.0f} potential customers × {money(a.arpu_monthly * 12)} a year
  = **{money(c.market.tam)}**
- **SAM** = TAM × {pct(m.serviceable_share, 0)} reachable with this offer and channel = **{money(c.market.sam)}**
- **SOM** = SAM × {pct(m.obtainable_share)} you can realistically win = **{money(c.market.som)}**

At the end of the projection you would hold **{money(s.ending_arr)}** of annual recurring revenue,
**{(s.ending_arr / c.market.som * 100) if c.market.som else 0:.0f}%** of the winnable market.
"""
    )

# ------------------------------------------------------------------------ projection
with tabs[3]:
    left, right = st.columns(2)
    left.plotly_chart(charts.customers_chart(c.projection), width="stretch")
    right.plotly_chart(charts.revenue_costs_chart(c.projection), width="stretch")
    st.plotly_chart(charts.cash_chart(c.projection, s), width="stretch")
    with st.expander("Monthly table"):
        monthly = c.projection.round(0)
        st.dataframe(monthly, hide_index=True, width="stretch")
        st.download_button(
            "Download projection (CSV)", monthly.to_csv(index=False), file_name=f"{idea.name}-projection.csv",
            mime="text/csv",
        )

# ----------------------------------------------------------------------- sensitivity
with tabs[4]:
    st.plotly_chart(charts.tornado(c.sensitivity, a.months), width="stretch")
    top = c.sensitivity.iloc[0]
    st.markdown(
        f"**{top['driver']}** moves the outcome most: a ±20% change shifts cash at month {a.months} by "
        f"**{money(top['impact_low'])}** / **{money(top['impact_high'])}**. "
        "Spend your validation effort on the drivers at the top of this chart."
    )

# ----------------------------------------------------------------------- AI analysis
with tabs[5]:
    if assessment is None:
        lead = "Click **Run AI analysis** above." if settings.live else NO_KEY_HINT
        st.info(f"{lead}\n\nFor this idea the analyst produces: the competitive landscape, a SWOT, key risks with "
                "mitigations, the questions an investor will ask and cheap experiments to validate demand.")
    else:
        st.markdown(f"#### {assessment.one_liner}")
        st.markdown(f"**Target customer:** {assessment.target_customer}  \n"
                    f"**Value proposition:** {assessment.value_proposition}")
        sw = assessment.swot
        r1 = st.columns(2)
        with r1[0]:
            card("💪 Strengths", sw.strengths)
        with r1[1]:
            card("⚠️ Weaknesses", sw.weaknesses)
        r2 = st.columns(2)
        with r2[0]:
            card("🚀 Opportunities", sw.opportunities)
        with r2[1]:
            card("🌩️ Threats", sw.threats)

        st.markdown("##### Key risks")
        table(["Risk", "Severity", "Mitigation"],
              [[r.risk, severity(r.severity), r.mitigation] for r in assessment.risks], html_cols=(1,))
        st.markdown("##### Competitors and substitutes")
        st.caption("Model-generated: verify each one before relying on it.")
        table(["Name", "Type", "How it compares"],
              [[x.name, x.kind.title(), x.note] for x in assessment.competitors])
        q_col, e_col = st.columns(2)
        with q_col:
            card("❓ Questions an investor will ask", assessment.investor_questions)
        with e_col:
            card("🧪 Cheap validation experiments", assessment.validation_experiments)

# -------------------------------------------------------------------- memo & report
with tabs[6]:
    memo = analysis["memo"] if analysis else None
    if memo:
        if freshness == "numbers_changed":
            st.warning("This memo was written before you changed the assumptions. Re-run the AI analysis to update it.")
        with st.container(border=True):
            st.markdown(re.sub(r"^#{1,3} ", "#### ", memo, flags=re.M))
    else:
        lead = "Click **Run AI analysis** above to write the investment memo." if settings.live else NO_KEY_HINT
        st.info(f"{lead}\n\nThe downloadable report below already includes every computed figure.")
    report = build_report(idea, a, m, c, scorecard, assessment, memo, analysis["model"] if analysis else None)
    st.download_button(
        "⬇️ Download full report (Markdown)", report, file_name=f"{idea.name}-venturelens-report.md",
        mime="text/markdown", type="primary",
    )

st.divider()
st.caption(
    "VentureLens AI is a decision-support tool, not investment advice. Every figure is computed from the "
    "assumptions in the sidebar; AI-generated content can be wrong and should be verified."
)
