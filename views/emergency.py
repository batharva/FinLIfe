from __future__ import annotations

import streamlit as st

from components import ui
from services import finance as fin
from views import _goal_shared as gs


def render(ctx) -> None:
    ds, m = ctx.ds, ctx.m
    ui.page_header("Emergency fund", "A cushion for the unexpected, kept separate from your other goals.")
    est = fin.essential_monthly_expense(ds.tx, 3, ctx.today) if len(ds.tx) else 0.0
    c1, c2 = st.columns(2)
    months = c1.radio("Months of essential expenses to cover", [3, 6, 12], index=1, horizontal=True)
    essential = c2.number_input("Essential monthly expenses", min_value=0.0, value=float(round(est, 0)), step=500.0,
                                help="Starts from your average 'need' spending over the last three complete months. Adjust it if that looks off.")
    if est == 0:
        st.caption("No 'need' spending recorded yet, so enter your estimate above.")
    target = fin.emergency_target(essential, months)
    goals = ds.goals[(ds.goals["goal_type"] == "emergency_fund") & (ds.goals["status"] != "cancelled")]
    goal = goals.iloc[0] if len(goals) else None
    contrib = gs.contributions_by_goal(ctx)
    allocated = float(goal["current_allocated_amount"]) + float(contrib.get(goal["id"], 0)) if goal is not None else 0.0
    remaining = max(target - allocated, 0.0)
    pct = min(allocated / target * 100, 100) if target else 0.0
    cover = allocated / essential if essential else 0.0

    k = st.columns(4)
    for col, (l, v, n) in zip(k, [("Target reserve", m(target), f"{months} months of essentials"), ("Saved so far", m(allocated), f"{cover:.1f} months covered"),
                                  ("Remaining", m(remaining), "to reach the target"), ("Progress", f"{pct:.0f}%", "")]):
        col.markdown(ui.kpi(l, v, note=n), unsafe_allow_html=True)
    ui.md(ui.progress(pct, "good" if pct >= 100 else "ok"))

    horizon = st.slider("I want to be fully funded in (months)", 1, 60, 12)
    need = remaining / horizon if horizon else remaining
    surplus, n = gs.surplus(ctx)
    rate = gs.recent_rate(ctx, goal["id"]) if goal is not None else 0.0
    st.markdown(f"**{m(need)} per month** for {horizon} months gets you there." +
                (f" That's {need / surplus * 100:.0f}% of your recent monthly surplus ({m(surplus)})." if surplus > 0 else " Your recent surplus isn't positive yet, so consider smaller steps or trimming wants first."))
    if remaining <= 0 and target > 0:
        st.success("Your emergency fund meets the target.")
    elif rate > 0:
        done = fin.add_months(ctx.today, int(-(-remaining // rate)))
        st.caption(f"At your recent pace of {m(rate)}/month you'd be fully funded around {done:%b %Y}.")
    else:
        st.caption("Add contributions below to get a completion estimate based on your actual pace.")

    from datetime import timedelta
    due = ctx.today + timedelta(days=int(horizon * 30.4375))
    if goal is None:
        if st.button("Start tracking my emergency fund", type="primary", disabled=target <= 0):
            ui.write(lambda: ctx.repo.insert("financial_goals", {"goal_name": "Emergency fund", "goal_type": "emergency_fund", "target_amount": round(target, 2),
                                                               "target_date": due.isoformat(), "priority": "high", "current_allocated_amount": 0, "status": "active"}),
                     "Emergency fund is now tracked.")
        return
    if abs(float(goal["target_amount"]) - target) > 1 and st.button("Update my saved target and deadline"):
        ui.write(lambda: ctx.repo.update("financial_goals", goal["id"], {"target_amount": round(target, 2), "target_date": due.isoformat()}), "Target updated.")
    st.markdown("#### Add to your emergency fund")
    gs.contribution_form(ctx, goal["id"], "emg")
