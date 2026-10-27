"""Small presentational helpers. All user-supplied text is HTML-escaped before it reaches unsafe_allow_html."""
from __future__ import annotations

import html
from typing import Callable

import pandas as pd
import streamlit as st

from services import data
from services.repo import DataError, SessionExpired

LOGO = ('<span class="fl-logo"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M4 19V9"/><path d="M10 19V5"/><path d="M16 19v-7"/>'
        '<path d="M3 19h18"/></svg></span>')


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def md(markup: str) -> None:
    st.markdown(markup.replace("\n", ""), unsafe_allow_html=True)


def brand() -> str:
    return f'<div class="fl-brand">{LOGO}<span>FinLife</span></div>'


def kpi(label: str, value: str, delta: str = "", delta_cls: str = "fl-flat", note: str = "") -> str:
    d = f'<span class="fl-delta {delta_cls}">{esc(delta)}</span>' if delta else ""
    return (f'<div class="fl-card"><div class="fl-kpi-label">{esc(label)}</div>'
            f'<div class="fl-kpi-value fl-num">{esc(value)}</div><div>{d}<span class="fl-kpi-note">{esc(note)}</span></div></div>')


def delta_badge(cur: float, prev: float | None, higher_is_better: bool = True, label: str = "") -> tuple[str, str]:
    """Month-over-month badge text and CSS class. Returns ('', 'fl-flat') when there is nothing to compare."""
    if prev is None or pd.isna(prev) or pd.isna(cur) or abs(prev) < 1e-9:
        return "", "fl-flat"
    ch = (cur - prev) / abs(prev) * 100
    if abs(ch) < 0.5:
        return f"0% {label}".strip(), "fl-flat"
    up = ch > 0
    good = up == higher_is_better
    return f"{'▲' if up else '▼'} {abs(ch):.0f}% {label}".strip(), "fl-up" if good else "fl-down"


TONE_COLOR = {"ok": "var(--primary)", "warn": "var(--warn)", "high": "var(--warn)", "over": "var(--bad)", "good": "var(--good)"}


def progress(pct: float, tone: str = "ok") -> str:
    w = max(0.0, min(float(pct), 100.0))
    return f'<div class="fl-bar"><div style="width:{w:.1f}%;background:{TONE_COLOR.get(tone, "var(--primary)")}"></div></div>'


def card(inner: str) -> str:
    return f'<div class="fl-card">{inner}</div>'


def empty_state(title: str, text: str) -> None:
    md(f'<div class="fl-card fl-empty"><div class="fl-title">{esc(title)}</div><div class="fl-muted">{esc(text)}</div></div>')


def html_table(df: pd.DataFrame, cols: list[tuple[str, str, str, Callable | None]]) -> None:
    """cols = [(column, header, 'l'|'r', formatter)]. Rendered as themed HTML (st.dataframe can't follow our theme)."""
    if df.empty:
        return
    head = "".join(f'<th class="{"r" if a == "r" else ""}">{esc(h)}</th>' for _, h, a, _ in cols)
    rows = []
    for _, r in df.iterrows():
        tds = []
        for key, _, a, fmt in cols:
            raw = r[key]
            if callable(fmt):
                out = fmt(raw)
                cell = out if isinstance(out, str) and out.startswith("<") else esc(out)
            else:
                cell = esc(raw)
            tds.append(f'<td class="{"r fl-num" if a == "r" else ""}">{cell}</td>')
        rows.append(f"<tr>{''.join(tds)}</tr>")
    md(f'<div class="fl-table-wrap"><table class="fl-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def tone_text(text: str, cls: str) -> str:
    return f'<span class="{cls}">{esc(text)}</span>'


def show_flash() -> None:
    if (n := st.session_state.pop("_flash", None)):
        st.toast(n[1], icon=":material/check_circle:" if n[0] == "success" else ":material/error:")


def flash(msg: str, kind: str = "success") -> None:
    st.session_state["_flash"] = (kind, msg)


def write(fn: Callable[[], object], ok: str, rerun: bool = True) -> bool:
    """Run a database write. On success: bump the data version, flash `ok`, rerun. On failure: show the error, keep the form."""
    try:
        fn()
    except SessionExpired:
        from services import auth
        auth.sign_out("Your session expired. Please sign in again.")
        st.rerun()
    except DataError as e:
        st.error(str(e))
        return False
    data.bump_version()
    flash(ok)
    if rerun:
        st.rerun()
    return True


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f"# {title}")
    if subtitle:
        st.caption(subtitle)
