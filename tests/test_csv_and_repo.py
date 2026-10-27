from datetime import date

import pandas as pd
import pytest

from services import csvio, recurring
from services.data import build_dataset
from services.repo import TABLES, DataError
from tests.fakes import FakeRepo, acct_id, cat_id, demo_history, seeded_repo


def ds_of(repo):
    return build_dataset({t: repo.select(t) for t in TABLES})


def test_seed_is_idempotent_and_complete():
    r = seeded_repo()
    n = len(r.select("categories"))
    r.seed_defaults()
    assert len(r.select("categories")) == n and len(r.select("accounts")) == 2
    names = {c["name"] for c in r.select("categories")}
    assert {"Rent or hostel", "Restaurants and cafés", "Internship stipend", "Stocks and ETFs"} <= names


# ---- ownership / authorization at the service layer --------------------------------
def test_user_id_cannot_be_spoofed_on_insert():
    store = {t: [] for t in TABLES}
    a, b = seeded_repo("user-a", store), seeded_repo("user-b", store)
    row = a.insert("budgets", {"user_id": "user-b", "category_id": cat_id(a, "Groceries"), "budget_amount": 1})[0]
    assert row["user_id"] == "user-a"


def test_users_cannot_read_update_or_delete_each_others_rows():
    store = {t: [] for t in TABLES}
    a, b = seeded_repo("user-a", store), seeded_repo("user-b", store)
    a.insert("transactions", {"account_id": acct_id(a), "transaction_type": "income", "amount": 100, "transaction_date": "2026-03-01"})
    tid = a.select("transactions")[0]["id"]
    assert b.select("transactions") == []
    b.update("transactions", tid, {"amount": 1})
    b.delete("transactions", tid)
    assert a.select("transactions")[0]["amount"] == 100


def test_real_repo_filters_every_write_by_user(monkeypatch):
    """The production Repo (not the fake) must add user_id filters - verified against a recording client."""
    from services.repo import Repo

    calls = []

    class Q:
        def __init__(self, name): self.name = name
        def __getattr__(self, m):
            def f(*a, **k):
                calls.append((self.name, m, a)); return self
            return f
        def execute(self):
            class R: data = [{"id": "x"}]
            return R()

    class C:
        def table(self, n): return Q(n)

    repo = Repo(C(), "user-a")
    repo.insert("transactions", {"user_id": "attacker", "amount": 5})
    repo.update("transactions", "t1", {"user_id": "attacker", "amount": 6})
    repo.delete("transactions", "t1")
    assert ("transactions", "insert", ([{"amount": 5, "user_id": "user-a"}],)) in calls
    assert calls.count(("transactions", "eq", ("user_id", "user-a"))) == 2        # update + delete both scoped
    with pytest.raises(ValueError):
        repo.select("auth.users")
    with pytest.raises(ValueError):
        Repo(C(), "")


def test_db_failures_become_user_safe_errors():
    import httpx
    from services.repo import _friendly, SessionExpired
    assert "too long" in str(_friendly(httpx.ReadTimeout("x")))
    assert "reach" in str(_friendly(httpx.ConnectError("x")))
    from postgrest.exceptions import APIError
    assert isinstance(_friendly(APIError({"message": "JWT expired", "code": "PGRST301"})), SessionExpired)
    assert "already exists" in str(_friendly(APIError({"message": "dup", "code": "23505"})))
    assert "secret" not in str(_friendly(RuntimeError("secret stack trace")))


# ---- CSV ---------------------------------------------------------------------------
def test_export_roundtrip_and_formula_injection_guard():
    r = seeded_repo()
    r.insert("transactions", {"account_id": acct_id(r), "category_id": cat_id(r, "Groceries"), "transaction_type": "expense", "amount": 250.5,
                              "transaction_date": "2026-03-04", "description": "=HYPERLINK(\"http://evil\")", "payment_method": "UPI", "notes": "+cmd"})
    ds = ds_of(r)
    raw = csvio.export_transactions(ds.tx, ds.accounts).decode("utf-8-sig")
    assert raw.splitlines()[0].startswith("date,type,amount")
    assert "'=HYPERLINK" in raw and "'+cmd" in raw and "250.50" in raw


def test_import_is_idempotent_and_reports_problems():
    r = seeded_repo()
    csv = (b"date,type,amount,description,category,account,payment_method\n"
           b"2026-03-01,income,50000,Pay,Salary,Bank account,Bank transfer\n"
           b"04/03/2026,expense,\xe2\x82\xb91,250.50,Lunch,Essential meals,Cash,UPI\n"
           b"2026-03-05,expense,-5,Bad,Groceries,Cash,UPI\n"
           b"notadate,expense,5,Bad,Groceries,Cash,UPI\n"
           b"2026-03-05,gift,5,Bad,Groceries,Cash,UPI\n"
           b"2026-03-06,expense,90,Taxi,Brand new cat,Nowhere,UPI\n"
           b"2026-03-07,expense,60,Chai,Brand new cat,Cash,UPI\n"
           b"2026-03-07,expense,60,Chai,Brand new cat,Cash,UPI\n")
    ds = ds_of(r)
    plan = csvio.parse_import(csv, ds.cats, ds.accounts, acct_id(r), ds.tx)
    assert len(plan.errors) >= 4 and len(plan.rows) == 3                    # salary, 2 identical chai (legit repeats)
    assert plan.new_categories == {"Brand new cat": "want"}
    # apply, then re-import: nothing new
    for row in plan.rows:
        r.insert("transactions", {k: v for k, v in row.items() if k != "category_name"})
    plan2 = csvio.parse_import(csv, ds_of(r).cats, ds_of(r).accounts, acct_id(r), ds_of(r).tx)
    assert plan2.rows == [] and plan2.duplicates == 3


def test_import_rejects_bad_files():
    ds = ds_of(seeded_repo())
    assert csvio.parse_import(b"foo,bar\n1,2\n", ds.cats, ds.accounts, "a", ds.tx).errors[0].startswith("Missing required")
    assert csvio.parse_import(b"\xff\xfe\x00bad", ds.cats, ds.accounts, "a", ds.tx).errors
    assert csvio.parse_import(b"", ds.cats, ds.accounts, "a", ds.tx).errors


# ---- recurring -----------------------------------------------------------------------
def test_recurring_posts_each_missed_period_once():
    r = seeded_repo()
    r.insert("recurring_transactions", {"description": "Rent", "transaction_type": "expense", "amount": 15000, "category_id": cat_id(r, "Rent or hostel"),
                                        "account_id": acct_id(r), "payment_method": "UPI", "frequency": "monthly", "next_due_date": "2026-01-31", "is_active": True})
    assert recurring.post_due(r, ds_of(r).recurring, date(2026, 3, 31)) == 3
    assert len(r.select("transactions")) == 3
    assert recurring.post_due(r, ds_of(r).recurring, date(2026, 3, 31)) == 0       # rerun creates no duplicates
    assert r.select("recurring_transactions")[0]["next_due_date"] == "2026-04-28"


def test_transfer_delete_removes_both_legs():
    r = seeded_repo()
    r.add_transfer(acct_id(r), acct_id(r, "Cash"), 500, date(2026, 3, 1), "ATM")
    t = r.select("transactions")
    assert len(t) == 2
    r.delete_transaction(t[0]["id"], t[0]["transfer_group_id"])
    assert r.select("transactions") == []
