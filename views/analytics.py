from __future__ import annotations

import pandas as pd
import streamlit as st

import plotly.graph_objects as go

from components import charts, ui
from components.theme import plotly_layout
from services import finance as fin
from utils.format import month_label, pct

RANGES = ["Selected month", "Last 3 months", "Last 6 months", "Last 12 months", "Custom range"]


def render(ctx) -> None:
    ds, m = ctx.ds, ctx.m
    ui.page_header("Analytics", "Where your money goes, and how that's changing.")
    if ds.tx.empty:
        return ui.empty_state("Nothing to analyse yet", "Record some transactions and trends will appear here.")
    choice = st.radio("Period", RANGES, index=1, horizontal=True)
    end_m = fin.month_end(ctx.month)
    if choice == "Custom range":
        lo, hi = ds.tx["transaction_date"].min().date(), ds.tx["transaction_date"].max().date()
        r = st.date_input("Dates", value=(max(lo, (end_m - pd.DateOffset(months=2)).date().replace(day=1)), min(hi, end_m.date())))
        if not isinstance(r, tuple) or len(r) != 2:
            return st.info("Pick a start and an end date.")
        start, end = pd.Timestamp(r[0]), pd.Timestamp(r[1])
    else:
        n = {"Selected month": 1, "Last 3 months": 3, "Last 6 months": 6, "Last 12 months": 12}[choice]
        start, end = fin.month_start(ctx.month) - pd.DateOffset(months=n - 1), end_m
    tx = ds.tx[(ds.tx["transaction_date"] >= start) & (ds.tx["transaction_date"] <= end)]
    if tx.empty:
        return st.info("No transactions in this period.")
    summary = fin.monthly_summary(tx)

    months_all = fin.distinct_months(ds.tx)
    st.caption(f"Based on {len(ds.tx)} transactions across {months_all} month(s), {ds.tx['transaction_date'].min():%d %b %Y} to "
               f"{ds.tx['transaction_date'].max():%d %b %Y}. This view covers {len(tx)} transactions from {start:%d %b %Y} to {end:%d %b %Y}.")
    if months_all < 3:
        st.info(f"You have {months_all} of 3 months recorded. Basic analytics are available now; the detailed three-month review unlocks after a third month of data.")

    avg = summary.mean(numeric_only=True)
    c = st.columns(4)
    rate = avg["savings"] / avg["income"] * 100 if avg["income"] > 0 else float("nan")
    for col, (lbl, val, note) in zip(c, [("Average monthly income", m(avg["income"]), f"over {len(summary)} month(s)"),
                                         ("Average monthly spending", m(avg["consumption"]), "after refunds"),
                                         ("Average monthly savings", m(avg["savings"]), f"{pct(rate)} of income" if pd.notna(rate) else "No income recorded"),
                                         ("Estimated surplus", m(avg["net_cash_flow"]), "after money invested")]):
        col.markdown(ui.kpi(lbl, val, note=note), unsafe_allow_html=True)
    if (summary["income"] == 0).any():
        st.caption("Some months have no income recorded, which lowers the averages and leaves savings rate blank for those months.")
    st.write("")

    a, b = st.columns(2)
    with a:
        st.markdown("### Income and spending by month")
        st.plotly_chart(charts.income_vs_expense(summary, ctx.cur), use_container_width=True, config={"displayModeBar": False})
    with b:
        st.markdown("### Spending by category")
        cs = fin.category_spend(ds.tx, start, end)
        if cs.empty:
            st.caption("No spending in this period.")
        else:
            st.plotly_chart(charts.category_bar(cs, ctx.cur), use_container_width=True, config={"displayModeBar": False})

    a, b = st.columns(2)
    with a:
        st.markdown("### Needs vs wants")
        nw = summary[["needs", "wants"]].copy()
        nw.index = [month_label(i) for i in nw.index]
        f = go.Figure([go.Bar(x=nw.index, y=nw["needs"], name="Needs", marker_color=charts.BLUE),
                       go.Bar(x=nw.index, y=nw["wants"], name="Wants", marker_color=charts.SKY)])
        f.update_layout(barmode="stack")
        st.plotly_chart(plotly_layout(f), use_container_width=True, config={"displayModeBar": False})
    with b:
        st.markdown("### Daily spending")
        st.plotly_chart(charts.daily_spending(tx, start, end, ctx.cur), use_container_width=True, config={"displayModeBar": False})

    st.markdown("### Month by month")
    t = summary.reset_index().sort_values("month", ascending=False)
    t["label"] = t["month"].map(month_label)
    t["chg"] = (t["consumption"] - t["consumption"].shift(-1)) / t["consumption"].shift(-1).replace(0, float("nan")) * 100
    ui.html_table(t, [("label", "Month", "l", None), ("income", "Income", "r", m), ("consumption", "Spending", "r", m),
                      ("investment", "Invested", "r", m), ("net_cash_flow", "Net cash flow", "r", m),
                      ("savings_rate", "Savings rate", "r", pct), ("chg", "Spending vs prior month", "r",
                                                                  lambda v: "—" if pd.isna(v) else f"{v:+.0f}%")])

    st.markdown("### Budget performance")
    spend = fin.category_spend(ds.tx, ctx.month, fin.month_end(ctx.month))
    rows = fin.budget_status(ds.budgets, ds.cats, spend, ctx.month, ctx.today) if len(ds.budgets) else []
    if rows:
        st.plotly_chart(charts.budget_performance(rows, ctx.cur), use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("Set budgets to see how you're tracking against them.")

    st.markdown("### Detailed three-month review")
    if months_all < 3:
        st.caption(f"Locked until three months of data are recorded ({months_all} so far).")
    else:
        full = ds.summary
        last3 = full.tail(3)
        best, worst = last3["savings"].idxmax(), last3["savings"].idxmin()
        st.markdown(f"- Last three months ({month_label(last3.index[0])} to {month_label(last3.index[-1])}): average spending **{m(last3['consumption'].mean())}**, "
                    f"average savings **{m(last3['savings'].mean())}**.\n"
                    f"- Strongest saving month: **{month_label(best)}** ({m(last3.loc[best, 'savings'])}). Weakest: **{month_label(worst)}** ({m(last3.loc[worst, 'savings'])}).")
        unusual = fin.unusual_months(full)
        if len(full) >= 4:
            if unusual.empty:
                st.markdown("- No month stands out as unusually high compared with your own history.")
            for ts, r in unusual.iterrows():
                st.markdown(f"- **{month_label(ts)}** was unusually high: {m(r['consumption'])} against a typical {m(full['consumption'].mean())}.")
        else:
            st.caption("Unusual-month detection needs four months of data.")
        rec = fin.recurring_expenses(ds.tx)
        st.markdown("**Recurring expenses detected** (same description in 3+ months, similar amounts)")
        if rec.empty:
            st.caption("None detected yet.")
        else:
            ui.html_table(rec, [("description", "Expense", "l", None), ("months", "Months seen", "r", None), ("avg_amount", "Typical amount", "r", m)])
        ins = fin.generate_insights(ds.tx, full, ctx.month, ctx.targets, m)
        st.markdown("**Observations** (simple rules applied to your own numbers - no machine learning)")
        if not ins:
            st.caption("Not enough comparison data for this month yet.")
        for i in ins:
            ui.md(f'<div class="fl-insight {i["tone"]}"><div class="fl-title">{ui.esc(i["title"])}</div><div class="fl-muted" style="font-size:.85rem">{ui.esc(i["detail"])}</div></div>')
