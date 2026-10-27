"""Pieces shared by Goals and Emergency Fund."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components import ui
from services import finance as fin

SOURCES = ["Monthly savings", "Bonus or windfall", "Gift", "Transfer from another goal", "Other"]


def tracked_assets(ctx) -> float:
    return fin.net_worth(ctx.ds.al, ctx.ds.accounts)["assets"]


def total_allocated(ctx) -> float:
    ds = ctx.ds
    open_goals = ds.goals[ds.goals["status"].isin(["active", "paused"])]
    base = pd.to_numeric(open_goals["current_allocated_amount"]).sum() if len(open_goals) else 0.0
    contrib = ds.contribs[ds.contribs["goal_id"].isin(open_goals["id"])]["amount"].astype(float).sum() if len(ds.contribs) else 0.0
    return float(base + contrib)


def contribution_form(ctx, goal_id: str, key: str) -> None:
    """Allocating money to a goal is an explicit decision, checked against savings you actually track."""
    pool, used = tracked_assets(ctx), total_allocated(ctx)
    free = pool - used
    with st.form(f"contrib_{key}", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        direction = c1.radio("Action", ["Add", "Withdraw"], horizontal=True, key=f"dir_{key}")
        amount = c2.number_input("Amount", min_value=0.0, step=500.0, format="%.2f", key=f"amt_{key}")
        on = c3.date_input("Date", value=ctx.today, max_value=ctx.today, key=f"dt_{key}")
        src = st.selectbox("Source", SOURCES, key=f"src_{key}")
        over = st.checkbox("Allocate even if it exceeds my tracked, unallocated savings", key=f"over_{key}")
        go = st.form_submit_button("Save", type="primary")
    st.caption(f"Tracked savings (accounts + assets): {ctx.m(pool)} · already assigned to goals: {ctx.m(used)} · unassigned: {ctx.m(free)}")
    if not go:
        return
    if amount <= 0:
        return st.error("Enter an amount greater than zero.")
    if direction == "Add" and pool > 0 and amount > free + 1e-9 and not over:
        return st.error(f"That's {ctx.m(amount - max(free, 0))} more than your unassigned savings. Reduce it, free up money from another goal, "
                        "or tick the override box to confirm you want it anyway.")
    signed = amount if direction == "Add" else -amount
    row = {"goal_id": goal_id, "amount": round(signed, 2), "contribution_date": on.isoformat(), "source": src}
    ui.write(lambda: ctx.repo.insert("goal_contributions", row), f"{'Added' if signed > 0 else 'Withdrew'} {ctx.m(amount, 2)}.")


def contributions_by_goal(ctx) -> pd.Series:
    c = ctx.ds.contribs
    return c.assign(amount=c["amount"].astype(float)).groupby("goal_id")["amount"].sum() if len(c) else pd.Series(dtype=float)


def recent_rate(ctx, goal_id: str) -> float:
    c = ctx.ds.contribs
    if c.empty:
        return 0.0
    c = c[(c["goal_id"] == goal_id)].copy()
    c["d"] = pd.to_datetime(c["contribution_date"])
    c = c[c["d"] >= pd.Timestamp(ctx.today) - pd.DateOffset(months=3)]
    return max(float(c["amount"].astype(float).sum()) / 3, 0.0)


def surplus(ctx) -> tuple[float, int]:
    """Average monthly savings (income - spending) over the last 3 complete months."""
    avg, n = fin.average_monthly(ctx.ds.summary, 3, ctx.today)
    return float(avg.get("savings", 0.0)), n
