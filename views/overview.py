from __future__ import annotations

import pandas as pd
import streamlit as st

from components import charts, ui
from services import finance as fin
from utils.format import month_label, pct


def render(ctx) -> None:
    ds, m = ctx.ds, ctx.m
    ui.page_header("Overview", f"Your money in {ctx.month:%B %Y}")
    if ds.tx.empty:
        ui.empty_state("Record your first transaction", "FinLife builds your dashboard from what you record. Add today's income or "
                       "an expense and this page comes alive. Nothing here is sample data.")
        if st.button("Add first transaction", type="primary", icon=":material/add:"):
            ctx.navigate("transactions")
            st.rerun()
        return

    summary = ds.summary
    mm = fin.month_metrics(summary, ctx.month)
    cur, prev = mm["current"], mm["previous"]
    pl = month_label(ctx.month - pd.DateOffset(months=1))
    p = lambda k: prev[k] if prev else None  # noqa: E731

    ncf_badge, ncf_cls = ui.delta_badge(cur["net_cash_flow"], p("net_cash_flow"), True, f"vs {pl}")
    rate = cur["savings_rate"]
    ui.md(f'<div class="fl-hero"><div class="fl-hero-label">Net cash flow in {ctx.month:%B}</div>'
          f'<div class="fl-hero-value fl-num">{ui.esc(m(cur["net_cash_flow"]))}</div>'
          f'<div style="opacity:.85;font-size:.9rem">{ui.esc(ncf_badge) or "Income minus spending minus money set aside"}</div>'
          f'<div class="fl-hero-row"><div><div>Came in</div><div class="fl-num">{ui.esc(m(cur["income"]))}</div></div>'
          f'<div><div>Spent</div><div class="fl-num">{ui.esc(m(cur["consumption"]))}</div></div>'
          f'<div><div>Saved &amp; invested</div><div class="fl-num">{ui.esc(m(cur["investment"]))}</div></div>'
          f'<div><div>Savings rate</div><div class="fl-num">{ui.esc(pct(rate) if pd.notna(rate) else "No income yet")}</div></div></div></div>')
    st.write("")

    bal = ds.accounts[ds.accounts["account_type"] != "credit_card"]["balance"].sum() if len(ds.accounts) else 0.0
    cols = st.columns(5)
    cards = [
        ("Income", m(cur["income"]), ui.delta_badge(cur["income"], p("income"), True, f"vs {pl}"), "Money received"),
        ("Spending", m(cur["consumption"]), ui.delta_badge(cur["consumption"], p("consumption"), False, f"vs {pl}"), "After refunds"),
        ("Savings", m(cur["savings"]), ui.delta_badge(cur["savings"], p("savings"), True, f"vs {pl}"),
         f"{pct(rate)} of income" if pd.notna(rate) else "Needs income to compute"),
        ("Invested", m(cur["investment"]), ui.delta_badge(cur["investment"], p("investment"), True, f"vs {pl}"), "Set aside, not spent"),
        ("Available balance", m(bal), ("", "fl-flat"), f"{len(ds.accounts[ds.accounts['account_type'] != 'credit_card'])} accounts"),
    ]
    for col, (label, val, (d, dc), note) in zip(cols, cards):
        col.markdown(ui.kpi(label, val, d, dc, note), unsafe_allow_html=True)
    st.write("")

    left, right = st.columns([1.7, 1])
    with left:
        st.markdown("### Income and spending")
        span = st.radio("Range", [3, 6, 12], index=1, horizontal=True, format_func=lambda n: f"Last {n} months", label_visibility="collapsed")
        end = fin.month_start(ctx.month)
        s = summary[(summary.index <= end) & (summary.index > end - pd.DateOffset(months=span))]
        if s.empty:
            st.caption("No activity in this range.")
        else:
            st.plotly_chart(charts.income_vs_expense(s, ctx.cur), use_container_width=True, config={"displayModeBar": False})
    with right:
        st.markdown("### Needs, wants, savings")
        alloc = fin.allocation(cur)
        if cur["income"] <= 0 and cur["consumption"] <= 0:
            st.caption(f"Nothing recorded in {ctx.month:%B %Y}.")
        else:
            st.plotly_chart(charts.allocation_donut(alloc, ctx.cur), use_container_width=True, config={"displayModeBar": False})
            t = ctx.targets
            st.caption(f"Targets: needs {t['needs']:.0f}% · wants {t['wants']:.0f}% · savings {t['savings']:.0f}%")
            if alloc["overspent"]:
                st.warning("Spending is higher than income this month, so no savings are shown.")

    a, b = st.columns(2)
    with a:
        st.markdown("### Recent transactions")
        recent = ds.tx[~ds.tx["transaction_type"].isin([])].sort_values(["transaction_date", "id"], ascending=False).head(8).copy()
        sign = {"income": "+", "refund": "+", "transfer_in": "+"}
        recent["amt"] = [f"{sign.get(t, '−')}{m(v)}" for t, v in zip(recent["transaction_type"], recent["amount"])]
        recent["when"] = recent["transaction_date"].dt.strftime("%d %b")
        recent["desc"] = recent["description"].where(recent["description"] != "", recent["category"])
        ui.html_table(recent, [("when", "Date", "l", None), ("desc", "Description", "l", None), ("category", "Category", "l", None),
                               ("amt", "Amount", "r", None)])
        st.write("")
        st.markdown("### Active goals")
        _goals(ctx)
    with b:
        st.markdown("### Budget status")
        _budgets(ctx)
        st.write("")
        st.markdown("### Insights")
        ins = fin.generate_insights(ds.tx, summary, ctx.month, ctx.targets, m)
        if not ins:
            st.caption("Insights appear once there's income and at least two earlier months to compare against.")
        for i in ins[:4]:
            ui.md(f'<div class="fl-insight {i["tone"]}"><div class="fl-title">{ui.esc(i["title"])}</div>'
                  f'<div class="fl-muted" style="font-size:.85rem">{ui.esc(i["detail"])}</div></div>')


def _goals(ctx) -> None:
    ds = ctx.ds
    g = ds.goals[ds.goals["status"] == "active"]
    if g.empty:
        st.caption("No active goals yet.")
        if st.button("Create a goal", key="ov_goal"):
            ctx.navigate("goals")
            st.rerun()
        return
    contrib = ds.contribs.groupby("goal_id")["amount"].sum() if len(ds.contribs) else pd.Series(dtype=float)
    for _, row in g.head(3).iterrows():
        gm = fin.goal_metrics(row.to_dict(), float(contrib.get(row["id"], 0)), ctx.today)
        ui.md(f'<div class="fl-card" style="margin-bottom:.6rem"><div class="fl-row"><span class="fl-title">{ui.esc(gm["name"])}</span>'
              f'<span class="fl-num">{gm["pct"]:.0f}%</span></div>{ui.progress(gm["pct"], "good" if gm["pct"] >= 100 else "ok")}'
              f'<div class="fl-kpi-note">{ui.esc(ctx.m(gm["allocated"]))} of {ui.esc(ctx.m(gm["adjusted_target"]))} · '
              f'{ui.esc(ctx.m(gm["required_monthly"]))}/month needed</div></div>')


def _budgets(ctx) -> None:
    ds = ctx.ds
    if ds.budgets.empty:
        st.caption("No budgets set.")
        if st.button("Set a budget", key="ov_budget"):
            ctx.navigate("budgets")
            st.rerun()
        return
    spend = fin.category_spend(ds.tx, ctx.month, fin.month_end(ctx.month))
    rows = fin.budget_status(ds.budgets, ds.cats, spend, ctx.month, ctx.today)
    for r in rows[:4]:
        ui.md(f'<div class="fl-card" style="margin-bottom:.6rem"><div class="fl-row"><span class="fl-title">{ui.esc(r["category"])}</span>'
              f'<span class="fl-num fl-{ "bad" if r["level"] == "over" else "warn" if r["level"] != "ok" else "muted"}">{r["pct"]:.0f}%</span></div>'
              f'{ui.progress(r["pct"], r["level"])}<div class="fl-kpi-note">{ui.esc(ctx.m(r["spent"]))} of {ui.esc(ctx.m(r["limit"]))}</div></div>')
