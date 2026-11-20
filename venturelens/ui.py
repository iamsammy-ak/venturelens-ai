"""Small HTML/CSS helpers for a polished Streamlit look (works in light and dark themes)."""

from __future__ import annotations

import html

import streamlit as st

ACCENT = "#7C3AED"
ACCENT_DARK = "#4C1D95"

_CSS = f"""
<style>
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1240px; }}
.vl-hero {{
  border-radius: 22px; padding: 30px 34px; margin-bottom: 1.2rem; color: #fff;
  background:
    radial-gradient(circle at 88% 18%, rgba(255,255,255,0.20), transparent 38%),
    radial-gradient(circle at 10% 110%, rgba(255,255,255,0.10), transparent 40%),
    linear-gradient(135deg, {ACCENT} 0%, {ACCENT_DARK} 100%);
  box-shadow: 0 18px 40px -22px rgba(76,29,149,0.65);
}}
.vl-hero .vl-title {{ font-size: 2.15rem; font-weight: 750; letter-spacing: -0.02em; line-height: 1.15; }}
.vl-hero .vl-sub {{ margin-top: 8px; font-size: 1.03rem; opacity: 0.92; max-width: 780px; }}
.vl-chip {{
  display: inline-block; margin: 14px 8px 0 0; padding: 4px 12px; border-radius: 999px;
  background: rgba(255,255,255,0.16); border: 1px solid rgba(255,255,255,0.22); font-size: 0.8rem;
}}
div[data-testid="stMetric"] {{
  border: 1px solid rgba(124,58,237,0.20); border-radius: 16px; padding: 14px 16px;
  background: linear-gradient(180deg, rgba(124,58,237,0.06), rgba(124,58,237,0.015));
}}
div[data-testid="stMetricLabel"] p {{ font-size: 0.82rem; opacity: 0.8; }}
div[data-testid="stMetricValue"] {{ font-size: 1.6rem; font-weight: 650; }}
.vl-card {{
  border: 1px solid rgba(148,163,184,0.35); border-radius: 16px; padding: 14px 18px; height: 100%;
}}
.vl-card h4 {{ margin: 0 0 6px 0; font-size: 0.95rem; }}
.vl-card ul {{ margin: 0; padding-left: 1.1rem; }}
.vl-pill {{
  display: inline-block; padding: 5px 14px; border-radius: 999px; font-weight: 600; font-size: 0.9rem;
  background: rgba(124,58,237,0.12); color: {ACCENT}; border: 1px solid rgba(124,58,237,0.25);
}}
.vl-table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; margin: 0.2rem 0 1rem 0; }}
.vl-table th {{
  text-align: left; font-weight: 600; opacity: 0.7; padding: 8px 10px;
  border-bottom: 1px solid rgba(148,163,184,0.45);
}}
.vl-table td {{ padding: 10px; border-bottom: 1px solid rgba(148,163,184,0.2); vertical-align: top; }}
.vl-table tr:hover td {{ background: rgba(124,58,237,0.03); }}
.vl-bar {{
  display: inline-block; width: 72px; height: 8px; border-radius: 99px; overflow: hidden;
  background: rgba(124,58,237,0.13); vertical-align: middle; margin-right: 8px;
}}
.vl-bar > div {{ height: 100%; border-radius: 99px; background: {ACCENT}; }}
.vl-num {{ font-weight: 650; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.vl-muted {{ opacity: 0.5; }}
.vl-sev-high {{ color: #DC2626; font-weight: 700; }}
.vl-sev-medium {{ color: #D97706; font-weight: 700; }}
.vl-sev-low {{ color: #059669; font-weight: 700; }}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str, chips: list[str]) -> None:
    chip_html = "".join(f'<span class="vl-chip">{html.escape(c)}</span>' for c in chips)
    st.markdown(
        f'<div class="vl-hero"><div class="vl-title">{html.escape(title)}</div>'
        f'<div class="vl-sub">{html.escape(subtitle)}</div>{chip_html}</div>',
        unsafe_allow_html=True,
    )


def pill(text: str) -> None:
    st.markdown(f'<span class="vl-pill">{html.escape(text)}</span>', unsafe_allow_html=True)


def table(headers: list[str], rows: list[list], html_cols: tuple[int, ...] = ()) -> None:
    """Render a wrapping HTML table. Cells are escaped unless their column is in `html_cols`."""
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>"
        + "".join(
            f"<td>{cell if i in html_cols else html.escape(str(cell))}</td>" for i, cell in enumerate(row)
        )
        + "</tr>"
        for row in rows
    )
    st.markdown(f'<table class="vl-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>',
                unsafe_allow_html=True)


def score_bar(value: float | None) -> str:
    if value is None:
        return '<span class="vl-muted">not scored</span>'
    width = max(0.0, min(100.0, value * 10))
    return (f'<span style="white-space:nowrap"><span class="vl-bar"><div style="width:{width:.0f}%"></div></span>'
            f'<span class="vl-num">{value:.1f}</span></span>')


def severity(level: str) -> str:
    level = level if level in ("low", "medium", "high") else "medium"
    return f'<span class="vl-sev-{level}">{level.title()}</span>'


def card(title: str, items: list[str]) -> None:
    body = "".join(f"<li>{html.escape(i)}</li>" for i in items) or "<li>—</li>"
    st.markdown(f'<div class="vl-card"><h4>{html.escape(title)}</h4><ul>{body}</ul></div>', unsafe_allow_html=True)
