from __future__ import annotations

from datetime import timedelta

import streamlit as st

from components import ui
from components.ctx import to_date
from services import finance as fin
from views import _goal_shared as gs

TYPES = {"car": "Car", "house": "House", "emergency_fund": "Emergency fund", "education": "Education / MBA", "travel": "Trip",
         "purchase": "Major purchase", "retirement": "Retirement", "other": "Other"}
STATE = {"affordable": ("Affordable", "fl-good"), "partial": ("Partly covered", "fl-warn"), "unfunded": ("Not covered", "fl-bad"),
         "complete": ("Fully funded", "fl-good")}


def render(ctx) -> None:
    ds = ctx.ds
    ui.page_header("Financial goals", "Plan big purchases with the numbers in front of you.")
    surplus, n = gs.surplus(ctx)
    contrib = gs.contributions_by_goal(ctx)
    metrics = [fin.goal_metrics(r.to_dict(), float(contrib.get(r["id"], 0)), ctx.today, gs.recent_rate(ctx, r["id"]))
               for _, r in ds.goals.iterrows()]
    feas = {g["id"]: g for g in fin.goal_feasibility(metrics, surplus)}

    c = st.columns(3)
    need_total = sum(g["required_monthly"] for g in metrics if g["status"] == "active" and g["remaining"] > 0)
    c[0].markdown(ui.kpi("Available monthly surplus", ctx.m(surplus), note=f"avg savings, last {n} month(s)" if n else "record income and spending first"), unsafe_allow_html=True)
    c[1].markdown(ui.kpi("Needed for all active goals", ctx.m(need_total), note="per month, no investment returns assumed"), unsafe_allow_html=True)
    c[2].markdown(ui.kpi("Assigned to goals", ctx.m(gs.total_allocated(ctx)), note=f"of {ctx.m(gs.tracked_assets(ctx))} tracked savings"), unsafe_allow_html=True)
    if n == 0:
        st.info("Feasibility is measured against your monthly surplus, which needs recorded income and spending.")
    elif need_total > surplus:
        st.warning(f"Your active goals need {ctx.m(need_total)} a month but your recent surplus is {ctx.m(surplus)}. See each goal for options.")
    st.write("")

    with st.expander("Create a goal", expanded=ds.goals.empty):
        with st.form("goal_new", clear_on_submit=True):
            name = st.text_input("Goal name", placeholder="e.g. Buy a car", max_chars=100)
            c1, c2 = st.columns(2)
            gtype = c1.selectbox("Type", list(TYPES), format_func=TYPES.get)
            prio = c2.selectbox("Priority", ["high", "medium", "low"], index=1, format_func=str.title)
            c3, c4 = st.columns(2)
            target = c3.number_input("Target amount (today's price)", min_value=0.0, step=10000.0, format="%.2f")
            tdate = c4.date_input("Target date", value=ctx.today + timedelta(days=365 * 2), min_value=ctx.today)
            c5, c6 = st.columns(2)
            infl = c5.number_input("Expected price inflation (% per year)", 0.0, 50.0, 0.0, 0.5, help="Raises the target to its expected future price.")
            have = c6.number_input("Already set aside for this goal", min_value=0.0, step=1000.0, format="%.2f")
            notes = st.text_input("Notes (optional)", max_chars=500)
            go = st.form_submit_button("Create goal", type="primary")
        if go:
            if not name.strip() or target <= 0:
                st.error("Give the goal a name and a target amount greater than zero.")
            else:
                row = {"goal_name": name.strip(), "goal_type": gtype, "target_amount": round(target, 2), "target_date": tdate.isoformat(),
                       "priority": "high" if gtype == "emergency_fund" and prio == "medium" else prio, "inflation_assumption": infl,
                       "current_allocated_amount": round(have, 2), "status": "active", "notes": notes.strip() or None}
                ui.write(lambda: ctx.repo.insert("financial_goals", row), "Goal created.")

    if ds.goals.empty:
        return ui.empty_state("No goals yet", "Create one above and FinLife will work out the monthly savings it needs.")
    for g in sorted(metrics, key=lambda x: (x["status"] != "active", fin.PRIORITY_ORDER.get(x["priority"], 1), x["target_date"])):
        _goal_card(ctx, g, feas.get(g["id"]), surplus)


def _goal_card(ctx, g, f, surplus) -> None:
    m = ctx.m
    label, cls = STATE.get(f["state"], ("", "fl-muted")) if f else (g["status"].title(), "fl-muted")
    infl = f" (≈ {m(g['adjusted_target'])} after {g['inflation']:.1f}% yearly inflation)" if g["inflation"] > 0 else ""
    est = ""
    if g["remaining"] > 0:
        est = (f"At your recent pace of {m(g['recent_rate'])}/month you'd finish around {g['est_completion']:%b %Y}" +
               (" - on time." if g["on_pace"] else " - after the target date.")) if g["est_completion"] else "No contributions in the last 3 months, so no completion estimate yet."
    status_html = f' · <span class="{cls}">{ui.esc(label)}</span>' if f else ''
    ui.md(f'<div class="fl-card" style="margin:.8rem 0 .3rem"><div class="fl-row"><span class="fl-title">{ui.esc(g["name"])} '
          f'<span class="fl-pill">{ui.esc(g["priority"].title())}</span> <span class="fl-pill">{ui.esc(gs_type(g["type"]))}</span></span>'
          f'<span class="fl-num fl-title">{g["pct"]:.0f}%</span></div>{ui.progress(g["pct"], "good" if g["pct"] >= 100 else "ok")}'
          f'<div class="fl-kpi-note">{ui.esc(m(g["allocated"]))} of {ui.esc(m(g["base_target"]))}{ui.esc(infl)} by {g["target_date"]:%d %b %Y} · '
          f'{ui.esc(m(g["remaining"]))} to go · {g["months_left"]} month(s) left</div>'
          f'<div style="margin-top:.5rem"><b class="fl-num">{ui.esc(m(g["required_monthly"]))}</b> <span class="fl-muted">needed per month</span>'
          f'{status_html}</div>'
          f'<div class="fl-kpi-note" style="margin-top:.2rem">{ui.esc(est)}</div></div>')
    if f and f["state"] in ("partial", "unfunded") and f["remaining"] > 0:
        avg_wants = float(ctx.ds.summary["wants"].tail(3).mean()) if len(ctx.ds.tx) else 0.0
        with st.expander("This goal isn't covered by your surplus. Options"):
            st.caption(f"Short by {m(f['shortfall'])} per month after higher-priority goals.")
            for o in fin.shortfall_options(f, max(surplus, 0), ctx.today, avg_wants):
                st.markdown(f"- {o}")
    with st.expander("Add or withdraw money · edit · delete"):
        gs.contribution_form(ctx, g["id"], g["id"])
        row = ctx.ds.goals[ctx.ds.goals["id"] == g["id"]].iloc[0]
        with st.form(f"edit_goal_{g['id']}"):
            n = st.text_input("Name", row["goal_name"])
            c1, c2, c3 = st.columns(3)
            t = c1.number_input("Target (today's price)", min_value=0.0, value=float(row["target_amount"]), step=10000.0)
            d = c2.date_input("Target date", value=to_date(row["target_date"]))
            i = c3.number_input("Inflation %", 0.0, 50.0, float(row["inflation_assumption"]), 0.5)
            c4, c5 = st.columns(2)
            p = c4.selectbox("Priority", ["high", "medium", "low"], index=["high", "medium", "low"].index(row["priority"]), format_func=str.title)
            s = c5.selectbox("Status", ["active", "paused", "completed", "cancelled"], index=["active", "paused", "completed", "cancelled"].index(row["status"]), format_func=str.title)
            save = st.form_submit_button("Save changes")
        if save and t > 0 and n.strip():
            vals = {"goal_name": n.strip(), "target_amount": round(t, 2), "target_date": d.isoformat(), "inflation_assumption": i, "priority": p, "status": s}
            ui.write(lambda: ctx.repo.update("financial_goals", g["id"], vals), "Goal updated.")
        if st.button("Delete goal and its contributions", key=f"delgoal_{g['id']}"):
            ui.write(lambda: ctx.repo.delete("financial_goals", g["id"]), "Goal deleted.")


def gs_type(t: str) -> str:
    return TYPES.get(t, t)
