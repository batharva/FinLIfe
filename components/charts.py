"""Plotly figures. Colours/grid/text follow the active theme (see components.theme)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from components.theme import plotly_layout
from utils.format import money

BLUE, SKY, GREEN, AMBER, RED, SLATE = "#2563EB", "#60A5FA", "#16A34A", "#D97706", "#DC2626", "#94A3B8"


def _m(values, cur):
    return [money(v, cur) for v in values]


def income_vs_expense(summary: pd.DataFrame, cur: str) -> go.Figure:
    f = go.Figure()
    x = summary.index
    for name, col, color in (("Income", "income", BLUE), ("Spending", "consumption", SKY)):
        f.add_bar(x=x, y=summary[col], name=name, marker_color=color, customdata=_m(summary[col], cur),
                  hovertemplate=name + ": %{customdata}<extra>%{x|%b %Y}</extra>")
    f.add_scatter(x=x, y=summary["net_cash_flow"], name="Net cash flow", mode="lines+markers", line=dict(color=GREEN, width=2.5),
                  customdata=_m(summary["net_cash_flow"], cur), hovertemplate="Net cash flow: %{customdata}<extra>%{x|%b %Y}</extra>")
    f.update_layout(barmode="group", bargap=.35)
    f.update_xaxes(tickformat="%b %Y", dtick="M1" if len(summary) <= 12 else None)
    return plotly_layout(f)


def allocation_donut(alloc: dict, cur: str) -> go.Figure:
    labels = [k for k in ("Needs", "Wants", "Savings", "Unclassified") if alloc.get(k, 0) > 0]
    vals = [alloc[k] for k in labels]
    colors = {"Needs": BLUE, "Wants": SKY, "Savings": GREEN, "Unclassified": SLATE}
    f = go.Figure(go.Pie(labels=labels, values=vals, hole=.62, sort=False, marker=dict(colors=[colors[k] for k in labels]),
                         customdata=_m(vals, cur), hovertemplate="%{label}: %{customdata} (%{percent})<extra></extra>",
                         textinfo="percent", textposition="outside"))
    return plotly_layout(f, height=300)


def category_bar(df: pd.DataFrame, cur: str, top: int = 10) -> go.Figure:
    d = df.head(top).iloc[::-1]
    f = go.Figure(go.Bar(x=d["amount"], y=d["category"], orientation="h", marker_color=BLUE, customdata=_m(d["amount"], cur),
                         hovertemplate="%{y}: %{customdata}<extra></extra>"))
    f.update_yaxes(gridcolor="rgba(0,0,0,0)")
    f.update_xaxes(showgrid=True, gridcolor="rgba(148,163,184,.25)")
    return plotly_layout(f, height=max(240, 34 * len(d) + 60), legend=False)


def daily_spending(tx: pd.DataFrame, start, end, cur: str) -> go.Figure:
    days = pd.date_range(start, end, freq="D")
    s = tx[tx["transaction_type"].isin(["expense", "refund"])].groupby(tx["transaction_date"].dt.normalize())["net_spend"].sum()
    s = s.reindex(days, fill_value=0.0)
    f = go.Figure()
    f.add_bar(x=s.index, y=s.values, name="Daily spending", marker_color=SKY, customdata=_m(s.values, cur),
              hovertemplate="%{customdata}<extra>%{x|%d %b %Y}</extra>")
    f.add_scatter(x=s.index, y=s.rolling(7, min_periods=1).mean(), name="7-day average", line=dict(color=BLUE, width=2.5),
                  hoverinfo="skip")
    return plotly_layout(f)


def budget_performance(rows: list[dict], cur: str) -> go.Figure:
    f = go.Figure()
    cats = [r["category"] for r in rows]
    f.add_bar(x=cats, y=[r["limit"] for r in rows], name="Budget", marker_color=SKY, customdata=_m([r["limit"] for r in rows], cur),
              hovertemplate="Budget: %{customdata}<extra>%{x}</extra>")
    f.add_bar(x=cats, y=[r["spent"] for r in rows], name="Spent", marker_color=[RED if r["pct"] >= 100 else BLUE for r in rows],
              customdata=_m([r["spent"] for r in rows], cur), hovertemplate="Spent: %{customdata}<extra>%{x}</extra>")
    f.update_layout(barmode="group", bargap=.3)
    return plotly_layout(f)


def networth_line(tl: pd.DataFrame, cur: str) -> go.Figure:
    f = go.Figure()
    for name, col, color in (("Assets", "assets", SKY), ("Liabilities", "liabilities", AMBER), ("Net worth", "net_worth", BLUE)):
        f.add_scatter(x=tl["date"], y=tl[col], name=name, mode="lines+markers", line=dict(color=color, width=3 if col == "net_worth" else 2),
                      customdata=_m(tl[col], cur), hovertemplate=name + ": %{customdata}<extra>%{x|%d %b %Y}</extra>")
    return plotly_layout(f)


def growth_chart(series: dict[str, pd.DataFrame], invested: pd.DataFrame, cur: str, goal_line: float | None = None) -> go.Figure:
    f = go.Figure()
    colors = [SKY, BLUE, GREEN]
    for (name, df), color in zip(series.items(), colors):
        f.add_scatter(x=df["month"] / 12, y=df["value"], name=name, line=dict(color=color, width=2.5),
                      customdata=_m(df["value"], cur), hovertemplate=name + ": %{customdata}<extra>Year %{x:.1f}</extra>")
    f.add_scatter(x=invested["month"] / 12, y=invested["invested"], name="Amount you put in", line=dict(color=SLATE, dash="dot", width=2),
                  customdata=_m(invested["invested"], cur), hovertemplate="You put in: %{customdata}<extra>Year %{x:.1f}</extra>")
    if goal_line:
        f.add_hline(y=goal_line, line=dict(color=AMBER, dash="dash"), annotation_text="Goal", annotation_position="top left")
    f.update_xaxes(title="Years")
    return plotly_layout(f, height=380)
