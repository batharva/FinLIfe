from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from components import ui
from components.ctx import CLASS_FOR_TYPE, TYPE_LABELS, account_choices, category_choices, clean, to_date
from services import csvio, recurring
from utils.defaults import PAYMENT_METHODS

ESSENTIAL = {"Use the category's default": None, "Essential": True, "Discretionary": False}


def render(ctx) -> None:
    ui.page_header("Transactions", "Record income and spending as it happens.")
    tabs = st.tabs(["Add", "History", "Recurring", "Import & export"])
    with tabs[0]:
        _add(ctx)
    with tabs[1]:
        _history(ctx)
    with tabs[2]:
        _recurring(ctx)
    with tabs[3]:
        _import_export(ctx)


# ---------------------------------------------------------------- add
def _add(ctx) -> None:
    ds = ctx.ds
    accounts = account_choices(ds.accounts)
    if not accounts:
        st.warning("Add an account in Settings first.")
        return
    kind = st.radio("Type", list(TYPE_LABELS), format_func=TYPE_LABELS.get, horizontal=True, key="add_kind")
    if kind == "transfer":
        return _transfer(ctx, accounts)
    cats = category_choices(ds.cats, CLASS_FOR_TYPE[kind])
    with st.form("add_tx", clear_on_submit=True):
        c1, c2 = st.columns(2)
        amount = c1.number_input("Amount", min_value=0.0, step=50.0, format="%.2f")
        on = c2.date_input("Date", value=ctx.today, max_value=ctx.today + timedelta(days=365))
        desc = st.text_input("Description", max_chars=200, placeholder="e.g. Lunch with friends")
        c3, c4 = st.columns(2)
        cat = c3.selectbox("Category", [None] + list(cats), format_func=lambda i: "Select..." if i is None else cats[i])
        acc = c4.selectbox("Account", list(accounts), format_func=accounts.get)
        c5, c6 = st.columns(2)
        pay = c5.selectbox("Payment method", PAYMENT_METHODS)
        ess = c6.selectbox("Essential?", list(ESSENTIAL), disabled=kind not in ("expense", "refund"))
        notes = st.text_input("Notes (optional)", max_chars=500)
        go = st.form_submit_button("Save transaction", type="primary", use_container_width=True)
    if not go:
        return
    if amount <= 0:
        return st.error("Enter an amount greater than zero.")
    if cat is None and not desc.strip():
        return st.error("Add a description or choose a category.")
    row = {"account_id": acc, "category_id": cat, "transaction_type": kind, "description": desc.strip(), "amount": round(amount, 2),
           "transaction_date": on.isoformat(), "payment_method": pay, "notes": notes.strip() or None,
           "is_essential": ESSENTIAL[ess] if kind in ("expense", "refund") else None}
    ui.write(lambda: ctx.repo.insert("transactions", row), f"Saved {TYPE_LABELS[kind].lower()} of {ctx.m(amount, 2)}.")


def _transfer(ctx, accounts) -> None:
    st.caption("Moving money between your own accounts, or paying a credit-card bill from a bank account, is neutral: "
               "it never counts as income or spending.")
    if len(accounts) < 2:
        return st.info("You need at least two accounts to record a transfer. Add one in Settings.")
    with st.form("transfer", clear_on_submit=True):
        c1, c2 = st.columns(2)
        src = c1.selectbox("From", list(accounts), format_func=accounts.get)
        dst = c2.selectbox("To", list(accounts), index=1, format_func=accounts.get)
        c3, c4 = st.columns(2)
        amount = c3.number_input("Amount", min_value=0.0, step=100.0, format="%.2f")
        on = c4.date_input("Date", value=ctx.today, max_value=ctx.today)
        desc = st.text_input("Description", value="Transfer", max_chars=200)
        go = st.form_submit_button("Save transfer", type="primary", use_container_width=True)
    if go:
        if src == dst:
            return st.error("Choose two different accounts.")
        if amount <= 0:
            return st.error("Enter an amount greater than zero.")
        ui.write(lambda: ctx.repo.add_transfer(src, dst, amount, on, desc.strip() or "Transfer"), f"Moved {ctx.m(amount, 2)}.")


# ---------------------------------------------------------------- history
def _history(ctx) -> None:
    ds, tx = ctx.ds, ctx.ds.tx
    if tx.empty:
        return ui.empty_state("No transactions yet", "Use the Add tab to record your first one.")
    accounts = account_choices(ds.accounts)
    f1, f2, f3, f4 = st.columns([1.2, 1, 1, 1])
    months = ["All time"] + [d.strftime("%Y-%m") for d in sorted(tx["transaction_date"].dt.to_period("M").dt.to_timestamp().unique(), reverse=True)]
    default = months.index(ctx.month.strftime("%Y-%m")) if ctx.month.strftime("%Y-%m") in months else 0
    mo = f1.selectbox("Month", months, index=default)
    ty = f2.selectbox("Type", ["All"] + list(TYPE_LABELS)[:-1] + ["transfer_in", "transfer_out"], format_func=lambda t: TYPE_LABELS.get(t, t.replace("_", " ").title()))
    cat = f3.selectbox("Category", ["All"] + sorted(tx["category"].unique()))
    pm = f4.selectbox("Payment", ["All"] + PAYMENT_METHODS)
    s1, s2 = st.columns([2, 1])
    q = s1.text_input("Search description", placeholder="Search...")
    sort = s2.selectbox("Sort by", ["Newest first", "Oldest first", "Highest amount", "Lowest amount"])
    v = tx
    if mo != "All time":
        v = v[v["transaction_date"].dt.strftime("%Y-%m") == mo]
    if ty != "All":
        v = v[v["transaction_type"] == ty]
    if cat != "All":
        v = v[v["category"] == cat]
    if pm != "All":
        v = v[v["payment_method"] == pm]
    if q.strip():
        v = v[v["description"].str.contains(q.strip(), case=False, na=False, regex=False)]
    by = {"Newest first": ("transaction_date", False), "Oldest first": ("transaction_date", True),
          "Highest amount": ("amount", False), "Lowest amount": ("amount", True)}[sort]
    v = v.sort_values(by[0], ascending=by[1], kind="stable")
    inc = v.loc[v["transaction_type"].isin(["income", "refund"]), "amount"].sum()
    out = v.loc[v["transaction_type"].isin(["expense", "investment"]), "amount"].sum()
    st.caption(f"{len(v)} transactions · in {ctx.m(inc)} · out {ctx.m(out)}" + (" · showing the first 200" if len(v) > 200 else ""))
    if v.empty:
        return st.info("Nothing matches those filters.")
    shown = v.head(200).copy()
    plus = {"income", "refund", "transfer_in"}
    shown["amt"] = [("+" if t in plus else "−") + ctx.m(a, 2) for t, a in zip(shown["transaction_type"], shown["amount"])]
    shown["when"] = shown["transaction_date"].dt.strftime("%d %b %Y")
    shown["acct"] = shown["account_id"].map(accounts)
    shown["kind"] = shown["transaction_type"].str.replace("_", " ").str.title()
    ui.html_table(shown, [("when", "Date", "l", None), ("description", "Description", "l", None), ("category", "Category", "l", None),
                          ("kind", "Type", "l", None), ("acct", "Account", "l", None), ("payment_method", "Payment", "l", None),
                          ("amt", "Amount", "r", None)])
    st.write("")
    _manage(ctx, v.head(200), accounts)


def _manage(ctx, v: pd.DataFrame, accounts) -> None:
    labels = {r["id"]: f"{r['transaction_date']:%d %b} · {r['description'] or r['category']} · {ctx.m(r['amount'], 2)}" for _, r in v.iterrows()}
    with st.expander("Edit, duplicate or delete a transaction"):
        tid = st.selectbox("Choose a transaction", list(labels), format_func=labels.get, key="manage_pick")
        r = v[v["id"] == tid].iloc[0]
        is_transfer = r["transaction_type"] in ("transfer_in", "transfer_out")
        if is_transfer:
            st.caption("Transfers have two linked entries. Deleting removes both.")
        else:
            kind = r["transaction_type"]
            cats = category_choices(ctx.ds.cats, CLASS_FOR_TYPE[kind])
            cur_cat = r["category_id"] if r["category_id"] in cats else None
            ess_label = {None: "Use the category's default", True: "Essential", False: "Discretionary"}[clean(r["is_essential"])]
            with st.form(f"edit_{tid}"):
                c1, c2 = st.columns(2)
                amount = c1.number_input("Amount", min_value=0.0, value=float(r["amount"]), step=50.0, format="%.2f")
                on = c2.date_input("Date", value=to_date(r["transaction_date"]))
                desc = st.text_input("Description", value=r["description"] or "", max_chars=200)
                c3, c4 = st.columns(2)
                cat = c3.selectbox("Category", [None] + list(cats), index=([None] + list(cats)).index(cur_cat),
                                   format_func=lambda i: "None" if i is None else cats[i])
                acc = c4.selectbox("Account", list(accounts), index=list(accounts).index(r["account_id"]), format_func=accounts.get)
                c5, c6 = st.columns(2)
                pay = c5.selectbox("Payment method", PAYMENT_METHODS, index=PAYMENT_METHODS.index(r["payment_method"]) if r["payment_method"] in PAYMENT_METHODS else 5)
                ess = c6.selectbox("Essential?", list(ESSENTIAL), index=list(ESSENTIAL).index(ess_label), disabled=kind not in ("expense", "refund"))
                notes = st.text_input("Notes", value=clean(r["notes"]) or "", max_chars=500)
                save = st.form_submit_button("Save changes", type="primary")
            if save:
                if amount <= 0:
                    return st.error("Amount must be greater than zero.")
                vals = {"account_id": acc, "category_id": cat, "description": desc.strip(), "amount": round(amount, 2),
                        "transaction_date": on.isoformat(), "payment_method": pay, "notes": notes.strip() or None,
                        "is_essential": ESSENTIAL[ess] if kind in ("expense", "refund") else None}
                ui.write(lambda: ctx.repo.update("transactions", tid, vals), "Transaction updated.")
            if st.button("Duplicate to today", key=f"dup_{tid}", icon=":material/content_copy:"):
                copy = {k: clean(r[k]) for k in ("account_id", "category_id", "transaction_type", "description", "amount", "payment_method", "notes", "is_essential")}
                copy["transaction_date"] = ctx.today.isoformat()
                copy["amount"] = float(copy["amount"])
                ui.write(lambda: ctx.repo.insert("transactions", copy), "Duplicated with today's date.")
        if st.session_state.get("_confirm_del") == tid:
            st.warning("Delete this transaction permanently?")
            a, b = st.columns(2)
            if a.button("Yes, delete", type="primary", key=f"yes_{tid}"):
                st.session_state.pop("_confirm_del", None)
                ui.write(lambda: ctx.repo.delete_transaction(tid, clean(r["transfer_group_id"])), "Transaction deleted.")
            if b.button("Cancel", key=f"no_{tid}"):
                st.session_state.pop("_confirm_del", None)
                st.rerun()
        elif st.button("Delete", key=f"del_{tid}", icon=":material/delete:"):
            st.session_state["_confirm_del"] = tid
            st.rerun()


# ---------------------------------------------------------------- recurring
def _recurring(ctx) -> None:
    ds = ctx.ds
    accounts = account_choices(ds.accounts)
    names = ds.cats.set_index("id")["name"] if len(ds.cats) else {}
    due_n = len(recurring.due_rows(ds.recurring, ctx.today)[0]) if len(ds.recurring) else 0
    if due_n:
        st.info(f"{due_n} recurring transaction(s) are due.")
        if st.button("Post due transactions", type="primary", icon=":material/event_repeat:"):
            ui.write(lambda: recurring.post_due(ctx.repo, ds.recurring, ctx.today), f"Posted {due_n} transaction(s).")
    kind = st.radio("Template type", ["expense", "income", "investment"], format_func=TYPE_LABELS.get, horizontal=True, key="rec_kind")
    cats = category_choices(ds.cats, CLASS_FOR_TYPE[kind])
    with st.form("rec_add", clear_on_submit=True):
        desc = st.text_input("Description", placeholder="e.g. Rent, Netflix, SIP", max_chars=200)
        c1, c2, c3 = st.columns(3)
        amount = c1.number_input("Amount", min_value=0.0, step=50.0, format="%.2f")
        freq = c2.selectbox("Repeats", ["monthly", "weekly", "quarterly", "yearly"])
        nxt = c3.date_input("Next due", value=ctx.today)
        c4, c5, c6 = st.columns(3)
        cat = c4.selectbox("Category", [None] + list(cats), format_func=lambda i: "None" if i is None else cats[i])
        acc = c5.selectbox("Account", list(accounts), format_func=accounts.get)
        pay = c6.selectbox("Payment method", PAYMENT_METHODS)
        go = st.form_submit_button("Save template", type="primary")
    if go:
        if amount <= 0 or not desc.strip():
            return st.error("Add a description and an amount greater than zero.")
        row = {"description": desc.strip(), "transaction_type": kind, "amount": round(amount, 2), "category_id": cat, "account_id": acc,
               "payment_method": pay, "frequency": freq, "next_due_date": nxt.isoformat(), "is_active": True}
        ui.write(lambda: ctx.repo.insert("recurring_transactions", row), "Recurring template saved.")
    if ds.recurring.empty:
        return st.caption("No templates yet.")
    for _, r in ds.recurring.iterrows():
        a, b, c = st.columns([4, 1, 1])
        state = "" if r["is_active"] else " (paused)"
        a.markdown(f"**{ui.esc(r['description'])}**{state}  \n{ctx.m(r['amount'], 2)} · {r['frequency']} · next {to_date(r['next_due_date']):%d %b %Y} · {ui.esc(names.get(r['category_id'], 'No category'))}")
        if b.button("Resume" if not r["is_active"] else "Pause", key=f"pz_{r['id']}"):
            ui.write(lambda: ctx.repo.update("recurring_transactions", r["id"], {"is_active": not r["is_active"]}), "Template updated.")
        if c.button("Delete", key=f"rd_{r['id']}"):
            ui.write(lambda: ctx.repo.delete("recurring_transactions", r["id"]), "Template deleted.")


# ---------------------------------------------------------------- import / export
def _import_export(ctx) -> None:
    ds = ctx.ds
    st.markdown("#### Export")
    if ds.tx.empty:
        st.caption("Nothing to export yet.")
    else:
        st.download_button("Download all transactions (CSV)", csvio.export_transactions(ds.tx, ds.accounts),
                           file_name=f"finlife-transactions-{ctx.today}.csv", mime="text/csv", icon=":material/download:")
    st.markdown("#### Import")
    st.caption("Columns: date, type (income/expense/investment/refund), amount, description, category, subcategory, account, "
               "payment_method, notes. Only date, type and amount are required. Re-importing the same file never creates duplicates.")
    st.download_button("Download a template", "date,type,amount,description,category,subcategory,account,payment_method,notes\n"
                       f"{ctx.today},expense,250,Lunch,Essential meals,,Cash,UPI,\n", file_name="finlife-import-template.csv", mime="text/csv")
    up = st.file_uploader("Choose a CSV file", type=["csv"], accept_multiple_files=False)
    if not up:
        return
    accounts = account_choices(ds.accounts)
    default = next(iter(accounts)) if accounts else ""
    plan = csvio.parse_import(up.getvalue(), ds.cats, ds.accounts, default, ds.tx)
    st.write(f"**{len(plan.rows)}** new · **{plan.duplicates}** already recorded (skipped) · **{len(plan.errors)}** problems")
    if plan.new_categories:
        st.info("New categories will be created (change their classification in Settings): " + ", ".join(plan.new_categories))
    for e in plan.errors[:15]:
        st.error(e)
    if len(plan.errors) > 15:
        st.caption(f"...and {len(plan.errors) - 15} more.")
    if plan.rows and st.button(f"Import {len(plan.rows)} transactions", type="primary"):
        ui.write(lambda: _do_import(ctx, plan), f"Imported {len(plan.rows)} transactions.")


def _do_import(ctx, plan) -> None:
    repo = ctx.repo
    ids = {str(n).lower(): i for n, i in zip(ctx.ds.cats["name"], ctx.ds.cats["id"])}
    if plan.new_categories:
        made = repo.insert("categories", [{"name": n, "financial_classification": c, "is_essential": False, "is_default": False}
                                          for n, c in plan.new_categories.items()])
        ids.update({m["name"].lower(): m["id"] for m in made})
    rows = [{**{k: v for k, v in r.items() if k != "category_name"}, "category_id": ids.get(r["category_name"].lower()) if r["category_name"] else None}
            for r in plan.rows]
    for i in range(0, len(rows), 500):
        repo.insert("transactions", rows[i:i + 500])
