from __future__ import annotations

import streamlit as st

from components import ui
from components.ctx import clean
from services import auth, csvio
from utils.defaults import ACCOUNT_TYPES
from utils.format import SYMBOLS

CLASSES = {"need": "Need", "want": "Want", "income": "Income", "saving": "Saving", "investment": "Investment"}
THEMES = {"light": "Light", "dark": "Dark", "system": "Match my device"}
ALL_TABLES = ["goal_contributions", "investment_plans", "budgets", "recurring_transactions", "transactions", "financial_goals",
              "assets_and_liabilities", "categories", "accounts"]


def render(ctx) -> None:
    ui.page_header("Settings")
    tabs = st.tabs(["Profile & appearance", "Accounts", "Categories", "Data & privacy"])
    with tabs[0]:
        _profile(ctx)
    with tabs[1]:
        _accounts(ctx)
    with tabs[2]:
        _categories(ctx)
    with tabs[3]:
        _data(ctx)


def _profile(ctx) -> None:
    p = ctx.profile
    with st.form("profile"):
        name = st.text_input("Full name", p.get("full_name") or "", max_chars=100)
        c1, c2 = st.columns(2)
        cur = c1.selectbox("Currency", list(SYMBOLS), index=list(SYMBOLS).index(p.get("preferred_currency", "INR")), format_func=lambda c: f"{c} ({SYMBOLS[c]})")
        theme = c2.selectbox("Theme", list(THEMES), index=list(THEMES).index(p.get("preferred_theme", "system")), format_func=THEMES.get)
        go = st.form_submit_button("Save", type="primary")
    st.caption(f"Signed in as {ctx.session.email}")
    if go:
        def _save():
            ctx.repo.update_profile({"full_name": name.strip(), "preferred_currency": cur, "preferred_theme": theme})
            st.session_state["_profile"] = None
        ui.write(_save, "Settings saved.")


def _accounts(ctx) -> None:
    ds = ctx.ds
    st.caption("Accounts hold your balances. Use a credit-card account for card spending, and record bill payments as transfers.")
    for _, a in ds.accounts.sort_values("account_name").iterrows():
        with st.expander(f"{a['account_name']} · {ACCOUNT_TYPES.get(a['account_type'], a['account_type'])} · {ctx.m(a['balance'], 2)}"):
            with st.form(f"acc_{a['id']}"):
                n = st.text_input("Name", a["account_name"], max_chars=60)
                t = st.selectbox("Type", list(ACCOUNT_TYPES), index=list(ACCOUNT_TYPES).index(a["account_type"]), format_func=ACCOUNT_TYPES.get)
                ob = st.number_input("Opening balance (negative for card debt)", value=float(a["opening_balance"]), step=100.0, format="%.2f")
                save = st.form_submit_button("Save account")
            if save and n.strip():
                ui.write(lambda: ctx.repo.update("accounts", a["id"], {"account_name": n.strip(), "account_type": t, "opening_balance": round(ob, 2)}), "Account updated.")
            used = len(ds.tx[ds.tx["account_id"] == a["id"]]) if len(ds.tx) else 0
            if used:
                st.caption(f"{used} transactions use this account, so it can't be deleted.")
            elif st.button("Delete account", key=f"delacc_{a['id']}"):
                ui.write(lambda: ctx.repo.delete("accounts", a["id"]), "Account deleted.")
    with st.form("acc_new", clear_on_submit=True):
        st.markdown("**Add an account**")
        c1, c2, c3 = st.columns(3)
        n = c1.text_input("Name", max_chars=60)
        t = c2.selectbox("Type", list(ACCOUNT_TYPES), format_func=ACCOUNT_TYPES.get)
        ob = c3.number_input("Opening balance", value=0.0, step=100.0, format="%.2f")
        go = st.form_submit_button("Add account", type="primary")
    if go:
        if not n.strip():
            st.error("Give the account a name.")
        else:
            ui.write(lambda: ctx.repo.insert("accounts", {"account_name": n.strip(), "account_type": t, "opening_balance": round(ob, 2), "currency": ctx.cur}), "Account added.")


def _categories(ctx) -> None:
    cats = ctx.ds.cats
    top = cats[cats["parent_category_id"].isna()].sort_values(["financial_classification", "name"])
    with st.form("cat_new", clear_on_submit=True):
        st.markdown("**Add a category or subcategory**")
        c1, c2, c3 = st.columns(3)
        n = c1.text_input("Name", max_chars=60)
        parent = c2.selectbox("Under", [None] + list(top["id"]), format_func=lambda i: "Top level" if i is None else top.set_index("id").loc[i, "name"])
        cl = c3.selectbox("Classification", list(CLASSES), format_func=CLASSES.get, help="Ignored for subcategories: they follow their parent.")
        go = st.form_submit_button("Add", type="primary")
    if go:
        if not n.strip():
            st.error("Give the category a name.")
        else:
            pc = top[top["id"] == parent].iloc[0]["financial_classification"] if parent else cl
            ui.write(lambda: ctx.repo.insert("categories", {"name": n.strip(), "parent_category_id": parent, "financial_classification": pc,
                                                           "is_essential": pc == "need", "is_default": False}), "Category added.")
    st.markdown("**Change classification or remove**")
    pick = st.selectbox("Category", list(cats["id"]), format_func=lambda i: cats.set_index("id").loc[i, "name"]) if len(cats) else None
    if pick:
        row = cats[cats["id"] == pick].iloc[0]
        c1, c2 = st.columns(2)
        new = c1.selectbox("Classification", list(CLASSES), index=list(CLASSES).index(row["financial_classification"]), format_func=CLASSES.get, key=f"cl_{pick}")
        if c1.button("Save classification", key=f"sc_{pick}"):
            ui.write(lambda: ctx.repo.update("categories", pick, {"financial_classification": new, "is_essential": new == "need"}), "Classification updated.")
        c2.caption("Deleting leaves existing transactions uncategorised.")
        if c2.button("Delete category", key=f"dc_{pick}"):
            ui.write(lambda: ctx.repo.delete("categories", pick), "Category deleted.")


def _data(ctx) -> None:
    ds = ctx.ds
    st.markdown("**Your data**  \nEverything is stored in your private account. You can download it or erase it.")
    if len(ds.tx):
        st.download_button("Download all transactions (CSV)", csvio.export_transactions(ds.tx, ds.accounts), "finlife-transactions.csv", "text/csv")
    st.markdown("**Erase all my financial data**")
    st.caption("Deletes transactions, budgets, goals, assets and categories. Your sign-in account stays. Account deletion itself is done by the service operator.")
    ok = st.text_input("Type DELETE to confirm", key="erase_confirm")
    if st.button("Erase everything", disabled=ok != "DELETE"):
        def _erase():
            for t in ALL_TABLES:
                for r in ctx.repo.select(t):
                    ctx.repo.delete(t, r["id"])
            ctx.repo.update_profile({"seeded": False})
            st.session_state["_profile"] = None
        ui.write(_erase, "All financial data erased.")
    st.divider()
    if st.button("Sign out of this device", icon=":material/logout:"):
        auth.sign_out("You've been signed out.")
        st.rerun()
