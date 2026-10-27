from __future__ import annotations

import pandas as pd
import streamlit as st

from components import ui
from components.ctx import category_choices
from services import finance as fin


def render(ctx) -> None:
    ds = ctx.ds
    ui.page_header("Budgets", f"Monthly limits by category · {ctx.month:%B %Y}")
    spend = fin.category_spend(ds.tx, ctx.month, fin.month_end(ctx.month)) if len(ds.tx) else fin.category_spend(ds.tx, ctx.month, ctx.month)
    rows = fin.budget_status(ds.budgets, ds.cats, spend, ctx.month, ctx.today) if len(ds.budgets) else []

    for r in rows:
        if r["crossed"]:
            msg = f"**{ui.esc(r['category'])}** is at {r['pct']:.0f}% of its {ctx.m(r['limit'])} budget (crossed {', '.join(str(c) + '%' for c in r['crossed'])})."
            (st.error if r["level"] == "over" else st.warning)(msg)

    if rows:
        for r in rows:
            proj = f" · on pace for {ctx.m(r['projected'])}" if r["projected"] != r["spent"] else ""
            rem = f"{ctx.m(r['remaining'])} left" if r["remaining"] >= 0 else f"{ctx.m(-r['remaining'])} over"
            ui.md(f'<div class="fl-card" style="margin-bottom:.6rem"><div class="fl-row"><span class="fl-title">{ui.esc(r["category"])}</span>'
                  f'<span class="fl-num">{r["pct"]:.0f}%</span></div>{ui.progress(r["pct"], r["level"])}'
                  f'<div class="fl-kpi-note">{ui.esc(ctx.m(r["spent"]))} of {ui.esc(ctx.m(r["limit"]))} · {ui.esc(rem)}{ui.esc(proj)}</div></div>')
    else:
        ui.empty_state("No budgets yet", "Set a monthly limit for a category below. Progress updates as you record transactions.")

    st.markdown("### Set or change a budget")
    cats = category_choices(ds.cats[ds.cats["parent_category_id"].isna()], {"need", "want"})
    if cats:
        with st.form("budget"):
            c1, c2 = st.columns(2)
            cat = c1.selectbox("Category", list(cats), format_func=cats.get)
            amount = c2.number_input("Monthly limit", min_value=0.0, step=500.0, format="%.2f")
            th = st.multiselect("Alert me at", [50, 75, 90, 100], default=[75, 90, 100], format_func=lambda x: f"{x}% of the limit")
            go = st.form_submit_button("Save budget", type="primary")
        if go:
            if amount <= 0:
                st.error("Enter a limit greater than zero.")
            else:
                existing = ds.budgets[ds.budgets["category_id"] == cat] if len(ds.budgets) else ds.budgets
                vals = {"budget_amount": round(amount, 2), "warning_thresholds": sorted(th) or [100]}
                if len(existing):
                    ui.write(lambda: ctx.repo.update("budgets", existing.iloc[0]["id"], vals), "Budget updated.")
                else:
                    ui.write(lambda: ctx.repo.insert("budgets", {"category_id": cat, "period": "monthly", **vals}), "Budget saved.")
    if rows:
        with st.expander("Remove a budget"):
            pick = st.selectbox("Budget", [r["budget_id"] for r in rows], format_func=lambda i: next(r["category"] for r in rows if r["budget_id"] == i))
            if st.button("Remove budget"):
                ui.write(lambda: ctx.repo.delete("budgets", pick), "Budget removed.")

    st.markdown("### Needs, wants and savings targets")
    st.caption("The 50/30/20 rule is a popular starting point, not a rule. Set whatever fits your life.")
    t = ctx.targets
    with st.form("targets"):
        c1, c2, c3 = st.columns(3)
        n = c1.number_input("Needs %", 0.0, 100.0, t["needs"], 5.0)
        w = c2.number_input("Wants %", 0.0, 100.0, t["wants"], 5.0)
        s = c3.number_input("Savings %", 0.0, 100.0, t["savings"], 5.0)
        a, b = st.columns(2)
        save = a.form_submit_button("Save targets", type="primary")
        preset = b.form_submit_button("Use 50/30/20")
    if preset:
        n, w, s, save = 50.0, 30.0, 20.0, True
    if save:
        if abs(n + w + s - 100) > 0.01:
            st.error(f"Targets add up to {n + w + s:.0f}%. They should total 100%.")
        else:
            def _save():
                ctx.repo.update_profile({"alloc_needs": n, "alloc_wants": w, "alloc_savings": s})
                st.session_state["_profile"] = None
            ui.write(_save, "Targets saved.")
    mm = fin.month_metrics(ds.summary, ctx.month)["current"] if len(ds.tx) else None
    if mm and mm["income"] > 0:
        a = fin.allocation(mm)
        inc = mm["income"]
        df = pd.DataFrame({"Bucket": ["Needs", "Wants", "Savings"], "Actual": [a["Needs"] / inc * 100, a["Wants"] / inc * 100, a["Savings"] / inc * 100],
                           "Target": [t["needs"], t["wants"], t["savings"]]})
        ui.html_table(df, [("Bucket", "Bucket", "l", None), ("Actual", "Actual", "r", lambda v: f"{v:.0f}%"), ("Target", "Target", "r", lambda v: f"{v:.0f}%")])
