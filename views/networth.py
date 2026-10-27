from __future__ import annotations

import pandas as pd
import streamlit as st

from components import charts, ui
from services import finance as fin

ASSET_CATS = ["Cash", "Bank balance", "Fixed deposit", "Mutual funds", "Stocks", "Other asset"]
LIAB_CATS = ["Education loan", "Personal loan", "Vehicle loan", "Credit card balance", "Other debt"]


def render(ctx) -> None:
    ds, m = ctx.ds, ctx.m
    ui.page_header("Net worth", "Assets minus liabilities, from values you enter yourself.")
    inc = st.toggle("Include account balances calculated from my transactions", value=True,
                    help="Turn this off if you also list your bank balances below, to avoid counting them twice.")
    nw = fin.net_worth(ds.al, ds.accounts, inc)
    k = st.columns(3)
    k[0].markdown(ui.kpi("Total assets", m(nw["assets"]), note=f"{m(nw['account_assets'])} in accounts · {m(nw['manual_assets'])} entered"), unsafe_allow_html=True)
    k[1].markdown(ui.kpi("Total liabilities", m(nw["liabilities"]), note=f"{m(nw['account_liabilities'])} on cards · {m(nw['manual_liabilities'])} entered"), unsafe_allow_html=True)
    k[2].markdown(ui.kpi("Net worth", m(nw["net_worth"]), note="assets − liabilities"), unsafe_allow_html=True)
    st.caption("Values are whatever you last entered or calculated from your transactions. FinLife does not connect to banks or fetch live market prices.")

    tl = fin.net_worth_timeline(ds.al)
    st.markdown("### Trend")
    if len(tl) >= 2:
        st.plotly_chart(charts.networth_line(tl, ctx.cur), use_container_width=True, config={"displayModeBar": False})
        st.caption("Trend uses the assets and liabilities you've entered, on the dates you valued them.")
    else:
        st.caption("Update your valuations on at least two different dates to see a trend.")

    st.markdown("### Add or update a value")
    cur = fin.latest_valuations(ds.al)
    with st.form("al_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        rtype = c1.radio("Type", ["asset", "liability"], horizontal=True, format_func=str.title)
        cat = c2.selectbox("Category", ASSET_CATS + LIAB_CATS)
        name = st.text_input("Name", placeholder="e.g. HDFC fixed deposit - using the same name later records a new valuation", max_chars=100)
        c3, c4 = st.columns(2)
        val = c3.number_input("Current value", min_value=0.0, step=1000.0, format="%.2f")
        on = c4.date_input("Valuation date", value=ctx.today, max_value=ctx.today)
        notes = st.text_input("Notes (optional)", max_chars=300)
        go = st.form_submit_button("Save", type="primary")
    if go:
        valid = (cat in ASSET_CATS) == (rtype == "asset")
        if not name.strip():
            st.error("Give it a name.")
        elif not valid:
            st.error(f"'{cat}' is not a {rtype} category.")
        else:
            ui.write(lambda: ctx.repo.insert("assets_and_liabilities", {"record_type": rtype, "name": name.strip(), "category": cat,
                                                                       "current_value": round(val, 2), "valuation_date": on.isoformat(), "notes": notes.strip() or None}),
                     "Saved.")

    for label, kind in (("Assets you entered", "asset"), ("Liabilities you entered", "liability")):
        st.markdown(f"### {label}")
        d = cur[cur["record_type"] == kind] if len(cur) else cur
        if d.empty:
            st.caption("None yet.")
            continue
        d = d.assign(when=d["valuation_date"].dt.strftime("%d %b %Y"))
        ui.html_table(d, [("name", "Name", "l", None), ("category", "Category", "l", None), ("when", "Valued on", "l", None), ("current_value", "Value", "r", m)])
        with st.expander(f"Remove {kind}s"):
            pick = st.selectbox("Choose", list(d["name"]), key=f"rm_{kind}")
            if st.button("Delete this item and its history", key=f"rmb_{kind}"):
                ids = ds.al[(ds.al["record_type"] == kind) & (ds.al["name"] == pick)]["id"].tolist()
                ui.write(lambda: [ctx.repo.delete("assets_and_liabilities", i) for i in ids], "Removed.")

    st.markdown("### Accounts (calculated from transactions)")
    if len(ds.accounts):
        ui.html_table(ds.accounts.sort_values("account_name"), [("account_name", "Account", "l", None), ("account_type", "Type", "l", lambda t: t.replace("_", " ").title()),
                                                                ("balance", "Balance", "r", lambda v: ctx.m(v, 2))])
