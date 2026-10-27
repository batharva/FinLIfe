from __future__ import annotations

import streamlit as st

from components import charts, ui
from services import finance as fin
from views import _goal_shared as gs

RISK = {"conservative": (4.0, 6.0, 7.5), "moderate": (5.0, 8.0, 11.0), "aggressive": (4.0, 10.0, 14.0)}

LEARN = {
    "Savings accounts": "Easy access and very low risk of losing principal, but interest may not keep up with inflation. Best for money you need soon.",
    "Fixed deposits (FD) and recurring deposits (RD)": "A fixed rate for a fixed term. Predictable, but breaking early usually costs interest and returns are usually taxable. Check deposit-insurance limits with your bank and DICGC.",
    "Liquid and debt mutual funds": "Hold short-term or bond-like instruments. Returns are not guaranteed: they move with interest rates (interest-rate risk) and issuer defaults (credit risk). Check the fund's portfolio and exit rules.",
    "Equity mutual funds and index funds": "Own shares of many companies. Over long periods they have historically beaten inflation, but values can fall sharply for years. Index funds track a market index at low cost; active funds charge more and may or may not do better.",
    "ETFs": "Index-tracking funds traded on a stock exchange through a demat account. Low costs, but prices move all day and you can lose money like any equity investment.",
    "Direct stocks": "Concentrated risk in single companies. Needs research, time and the ability to absorb large losses. Most beginners start with diversified funds.",
    "Retirement-oriented options (EPF, PPF, NPS)": "Designed for long horizons with lock-ins or withdrawal rules. Rules, limits and tax treatment change, so read the current terms on the official sites.",
}
RISKS = [("Market risk", "Prices rise and fall. Equity can lose a lot in the short term."), ("Interest-rate risk", "When rates rise, existing bond and debt-fund prices tend to fall."),
         ("Credit risk", "The borrower may fail to pay you back."), ("Inflation", "Prices rise over time; money earning less than inflation loses buying power."),
         ("Fees", "A 1% yearly cost compounds into a large gap over decades."), ("Liquidity", "How quickly you can turn it into cash without loss."),
         ("Taxes", "Tax treatment differs by product and changes over time. Verify on incometax.gov.in or with a qualified adviser.")]


def _horizon_note(years: float) -> str:
    if years < 1:
        return "Under a year: prioritise access to your money and capital safety (savings account, liquid options, short deposits). Equity is a poor fit for money needed this soon."
    if years < 3:
        return "1 to 3 years: favour safety and liquidity (deposits, high-quality short-term debt options). A bad market year could land right before you need the money, so equity is usually a poor fit for the main part."
    if years < 5:
        return "3 to 5 years: a mix may be considered, but losses are possible close to the deadline. Many people keep most of the goal in lower-risk options and de-risk as the date nears."
    return "5+ years: diversified equity exposure (such as broad index funds) may be considered if you can tolerate large temporary losses. Match the amount to your risk tolerance, not just the horizon."


def render(ctx) -> None:
    ds, m = ctx.ds, ctx.m
    ui.page_header("Investment planner", "Explore what-if scenarios. Educational only - not personal advice, and returns are never guaranteed.")
    st.markdown("### 1. Are you ready to invest?")
    essential = fin.essential_monthly_expense(ds.tx, 3, ctx.today) if len(ds.tx) else 0.0
    emg = ds.goals[(ds.goals["goal_type"] == "emergency_fund") & (ds.goals["status"] != "cancelled")]
    contrib = gs.contributions_by_goal(ctx)
    emg_saved = float(emg.iloc[0]["current_allocated_amount"]) + float(contrib.get(emg.iloc[0]["id"], 0)) if len(emg) else 0.0
    cover = emg_saved / essential if essential else 0.0
    nw = fin.net_worth(ds.al, ds.accounts)
    surplus, _ = gs.surplus(ctx)
    items = [("Emergency fund", f"{cover:.1f} months of essentials saved" if essential else "Record some spending to size it", cover >= 3),
             ("Debts", f"{m(nw['liabilities'])} owed. Paying off costly debt is often a better 'return' than investing." if nw["liabilities"] else "No debts recorded", nw["liabilities"] == 0),
             ("Monthly surplus", f"{m(surplus)} available" if surplus > 0 else "No recent surplus", surplus > 0)]
    for t, d, ok in items:
        st.markdown(f"{':material/check_circle:' if ok else ':material/warning:'} **{t}:** {d}")

    st.markdown("### 2. Compare scenarios")
    goals = ds.goals[ds.goals["status"] == "active"]
    opts = {"": "No goal (free exploration)", **{r["id"]: r["goal_name"] for _, r in goals.iterrows()}}
    gid = st.selectbox("Link to a goal (optional)", list(opts), format_func=opts.get)
    target = years_default = None
    if gid:
        g = goals[goals["id"] == gid].iloc[0]
        gm = fin.goal_metrics(g.to_dict(), float(contrib.get(gid, 0)), ctx.today)
        target, years_default = gm["adjusted_target"], max(gm["months_left"] / 12, 0.25)
    risk = st.selectbox("Risk comfort", list(RISK), index=1, format_func=str.title)
    lo0, mid0, hi0 = RISK[risk]
    c1, c2, c3 = st.columns(3)
    initial = c1.number_input("Starting amount", min_value=0.0, value=float(gm["allocated"]) if gid else 0.0, step=5000.0)
    monthly = c2.number_input("Monthly contribution", min_value=0.0, value=float(round(gm["required_monthly"], -2)) if gid else 5000.0, step=500.0)
    years = c3.number_input("Years", min_value=0.25, max_value=50.0, value=float(round(years_default, 2)) if years_default else 5.0, step=0.5)
    r1, r2, r3, r4 = st.columns(4)
    lo = r1.number_input("Lower return % / yr", -5.0, 30.0, lo0, 0.5)
    mid = r2.number_input("Middle return % / yr", -5.0, 30.0, mid0, 0.5)
    hi = r3.number_input("Higher return % / yr", -5.0, 30.0, hi0, 0.5)
    fee = r4.number_input("Yearly costs %", 0.0, 5.0, 0.5, 0.1)
    st.caption("These are assumptions you can change, not forecasts. Real returns can be lower than your lower case, including negative.")
    st.info(_horizon_note(years))

    series = {f"{n} ({r:g}%)": fin.growth_series(initial, monthly, r, years, fee) for n, r in (("Lower", lo), ("Middle", mid), ("Higher", hi))}
    invested = fin.growth_series(initial, monthly, 0, years, 0)
    st.plotly_chart(charts.growth_chart(series, invested, ctx.cur, target), use_container_width=True, config={"displayModeBar": False})
    rows = []
    for (name, df), r in zip(series.items(), (lo, mid, hi)):
        end = df["value"].iloc[-1]
        row = {"Scenario": name, "End value": m(end), "You put in": m(invested["invested"].iloc[-1]), "Growth": m(end - invested["invested"].iloc[-1])}
        if target:
            need = fin.required_monthly(target, int(round(years * 12)), r, initial, fee)
            row["Monthly needed for goal"] = m(need)
            row["Goal met?"] = "Yes" if end >= target else f"Short by {m(target - end)}"
        rows.append(row)
    import pandas as pd
    t = pd.DataFrame(rows)
    ui.html_table(t, [(c, c, "l" if c == "Scenario" else "r", None) for c in t.columns])
    if target:
        st.caption(f"Goal target including inflation: {m(target)}. 'Monthly needed' assumes that scenario's return after yearly costs.")

    if st.button("Save this scenario", icon=":material/save:"):
        ui.write(lambda: ctx.repo.insert("investment_plans", {"goal_id": gid or None, "plan_name": f"{risk.title()} scenario", "initial_amount": initial,
                                                             "monthly_contribution": monthly, "investment_horizon": years, "risk_profile": risk,
                                                             "return_assumption": mid, "low_return": lo, "high_return": hi, "fee_assumption": fee}), "Scenario saved.")
    if len(ds.plans):
        with st.expander(f"Saved scenarios ({len(ds.plans)})"):
            for _, p in ds.plans.sort_values("created_at", ascending=False).iterrows():
                a, b = st.columns([5, 1])
                a.markdown(f"**{ui.esc(p['plan_name'])}** · {m(p['initial_amount'])} + {m(p['monthly_contribution'])}/month for {float(p['investment_horizon']):g} yrs · "
                           f"{p['low_return']}% / {p['return_assumption']}% / {p['high_return']}% less {p['fee_assumption']}% costs")
                if b.button("Delete", key=f"dp_{p['id']}"):
                    ui.write(lambda: ctx.repo.delete("investment_plans", p["id"]), "Scenario deleted.")

    st.markdown("### 3. Learn the options")
    for k, v in LEARN.items():
        with st.expander(k):
            st.write(v)
    with st.expander("Risks to understand"):
        for k, v in RISKS:
            st.markdown(f"**{k}.** {v}")
    st.caption("FinLife never places trades or asks for brokerage or bank credentials. Check current rules with official sources: "
               "[RBI](https://www.rbi.org.in) · [SEBI](https://www.sebi.gov.in) · [AMFI](https://www.amfiindia.com) · [Income Tax Department](https://www.incometax.gov.in).")
