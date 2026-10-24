"""Small layout helpers shared by the sections."""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from utils.viz import PLOTLY_CONFIG


def headline(text: str) -> None:
    """One-sentence insight that opens a section."""
    st.markdown(f"<p class='headline'>{text}</p>", unsafe_allow_html=True)


def chart(fig, alt: str, key: str, table: pd.DataFrame | None = None, table_label: str = "Show the data") -> None:
    """Plotly chart followed by its text description (read by screen readers
    as normal text) and an optional data table, so no value depends on color."""
    st.plotly_chart(fig, config=PLOTLY_CONFIG, key=key)
    st.caption(f"Chart description: {alt}")
    if table is not None and not table.empty:
        with st.expander(table_label):
            st.dataframe(table, hide_index=True)


def n(v, digits: int = 0) -> str:
    """Format a number for prose; 'n/a' when it is missing."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{v:,.{digits}f}"


def rate(v) -> str:
    """A per-100k style rate: whole numbers, one decimal below 10."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{v:,.1f}" if abs(v) < 10 else f"{v:,.0f}"


def plural(k, word: str, words: str | None = None) -> str:
    return f"{n(k)} {word if k == 1 else (words or word + 's')}"


def compare(a: float, b: float, tol: float = 0.05) -> str:
    """'level with', 'ahead of' or 'behind' for a vs b, with a relative tolerance."""
    if b == 0 or a != a or b != b:
        return "compared with"
    r = a / b - 1
    return "level with" if abs(r) <= tol else ("ahead of" if r > 0 else "behind")


def pct(v, digits: int = 0) -> str:
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{digits}f}%"


def names(items, limit: int = 4) -> str:
    items = list(items)
    if not items:
        return "none"
    if len(items) > limit:
        rest = len(items) - limit
        return ", ".join(items[:limit]) + f" and {rest} other{'s' if rest > 1 else ''}"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


CSS = """
<style>
.headline {font-size: 1.15rem; font-weight: 600; color: #0d366b; margin: 0.2rem 0 0.8rem 0;
           border-left: 4px solid #2a78d6; padding-left: 0.7rem; line-height: 1.45;}
[data-testid="stMetricValue"] {font-size: 1.7rem;}
[data-testid="stCaptionContainer"] p {color: #52514e;}
</style>
"""
