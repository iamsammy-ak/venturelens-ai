"""Human-friendly number formatting shared by the UI, the memo facts and the report."""

from __future__ import annotations

import math


def money(value: float | None, currency: str = "€") -> str:
    if value is None:
        return "—"
    if math.isinf(value):
        return "∞"
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1e9:
        body = f"{v / 1e9:.1f}B"
    elif v >= 1e6:
        body = f"{v / 1e6:.1f}M"
    elif v >= 1e4:
        body = f"{v / 1e3:.0f}k"
    elif v >= 1e3:
        body = f"{v / 1e3:.1f}k"
    else:
        body = f"{v:,.0f}"
    return f"{sign}{currency}{body}"


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def ratio(value: float) -> str:
    return "∞" if math.isinf(value) else f"{value:.1f}×"


def months(value: float | None, *, never: str = "Never") -> str:
    if value is None or math.isinf(value):
        return never
    return f"{value:.1f} months" if value % 1 else f"{int(value)} months"


def month_label(month: int | None, horizon: int) -> str:
    return f"Month {month}" if month is not None else f"Not within {horizon} months"
