from datetime import date

import numpy as np
import pandas as pd
import pytest

from services import finance as fin
from tests.fakes import acct_id, cat_id, demo_history, seeded_repo
from services.data import build_dataset
from services.repo import TABLES


def dataset(repo):
    return build_dataset({t: repo.select(t) for t in TABLES})


def tx(repo, kind, amount, on, cat=None, desc="", account=None, **kw):
    repo.insert("transactions", {"account_id": account or acct_id(repo), "category_id": cat_id(repo, cat) if cat else None, "transaction_type": kind,
                                 "amount": amount, "transaction_date": on, "description": desc, "payment_method": "UPI", **kw})


def test_empty_dataset_is_safe():
    ds = dataset(seeded_repo())
    assert ds.tx.empty and ds.summary.empty
    assert fin.month_metrics(ds.summary, "2026-03-01")["current"]["income"] == 0
    assert fin.average_monthly(ds.summary)[1] == 0
    assert fin.category_spend(ds.tx, "2026-01-01", "2026-12-31").empty


def test_income_expense_and_savings_rate():
    r = seeded_repo()
    tx(r, "income", 50000, "2026-03-01", "Salary")
    tx(r, "expense", 10000, "2026-03-05", "Groceries")
    tx(r, "investment", 5000, "2026-03-10", "Mutual funds")
    m = fin.month_metrics(dataset(r).summary, "2026-03-15")["current"]
    assert m["income"] == 50000 and m["consumption"] == 10000 and m["investment"] == 5000
    assert m["savings"] == 40000                       # investments are saved, not spent
    assert m["net_cash_flow"] == 35000
    assert m["savings_rate"] == pytest.approx(80.0)


def test_missing_income_gives_nan_rate_not_crash():
    r = seeded_repo()
    tx(r, "expense", 700, "2026-03-05", "Groceries")
    m = fin.month_metrics(dataset(r).summary, "2026-03-01")["current"]
    assert np.isnan(m["savings_rate"]) and m["savings"] == -700


def test_transfer_is_neutral_and_moves_balances():
    r = seeded_repo()
    bank, cash = acct_id(r), acct_id(r, "Cash")
    tx(r, "income", 10000, "2026-03-01", "Salary")
    r.add_transfer(bank, cash, 2000, date(2026, 3, 2), "ATM")
    ds = dataset(r)
    m = fin.month_metrics(ds.summary, "2026-03-01")["current"]
    assert m["income"] == 10000 and m["consumption"] == 0 and m["investment"] == 0
    bal = ds.accounts.set_index("account_name")["balance"]
    assert bal["Bank account"] == 8000 and bal["Cash"] == 2000


def test_credit_card_purchase_counts_once_and_bill_payment_is_not_an_expense():
    r = seeded_repo()
    r.insert("accounts", {"account_name": "Card", "account_type": "credit_card", "opening_balance": 0, "currency": "INR"})
    card, bank = acct_id(r, "Card"), acct_id(r)
    tx(r, "income", 30000, "2026-03-01", "Salary")
    tx(r, "expense", 5000, "2026-03-04", "Shopping", account=card)
    ds = dataset(r)
    assert fin.month_metrics(ds.summary, "2026-03-01")["current"]["consumption"] == 5000
    assert ds.accounts.set_index("account_name").loc["Card", "balance"] == -5000       # liability
    r.add_transfer(bank, card, 5000, date(2026, 4, 2), "Card bill")
    ds = dataset(r)
    assert ds.summary["consumption"].sum() == 5000                                      # not double counted
    bal = ds.accounts.set_index("account_name")["balance"]
    assert bal["Card"] == 0 and bal["Bank account"] == 30000 - 5000
    assert fin.net_worth(ds.al, ds.accounts)["net_worth"] == 25000


def test_refund_reduces_consumption_and_category_spend():
    r = seeded_repo()
    tx(r, "expense", 3000, "2026-03-04", "Shopping")
    tx(r, "refund", 1000, "2026-03-09", "Shopping")
    ds = dataset(r)
    assert fin.month_metrics(ds.summary, "2026-03-01")["current"]["consumption"] == 2000
    cs = fin.category_spend(ds.tx, "2026-03-01", "2026-03-31")
    assert cs.loc[cs["category"] == "Shopping", "amount"].iloc[0] == 2000


def test_needs_wants_classification_and_override():
    r = seeded_repo()
    tx(r, "expense", 1000, "2026-03-04", "Groceries")                 # need
    tx(r, "expense", 400, "2026-03-05", "Shopping")                   # want
    tx(r, "expense", 300, "2026-03-06", "Shopping", is_essential=True)  # override -> need
    m = fin.month_metrics(dataset(r).summary, "2026-03-01")["current"]
    assert m["needs"] == 1300 and m["wants"] == 400


def test_date_boundaries_month_end_and_start():
    r = seeded_repo()
    tx(r, "expense", 100, "2026-03-31", "Groceries")
    tx(r, "expense", 200, "2026-04-01", "Groceries")
    s = dataset(r).summary
    assert s.loc["2026-03-01", "consumption"] == 100 and s.loc["2026-04-01", "consumption"] == 200
    ds = dataset(r)
    assert fin.category_spend(ds.tx, "2026-03-01", fin.month_end("2026-03-15"))["amount"].sum() == 100


def test_empty_months_are_filled_with_zero():
    r = seeded_repo()
    tx(r, "income", 100, "2026-01-10", "Salary")
    tx(r, "income", 100, "2026-04-10", "Salary")
    s = dataset(r).summary
    assert len(s) == 4 and s.loc["2026-02-01", "income"] == 0


def test_budget_progress_levels_and_projection():
    r = seeded_repo()
    tx(r, "expense", 4600, "2026-03-05", "Groceries")
    r.insert("budgets", {"category_id": cat_id(r, "Groceries"), "period": "monthly", "budget_amount": 5000, "warning_thresholds": [75, 90, 100]})
    ds = dataset(r)
    spend = fin.category_spend(ds.tx, "2026-03-01", "2026-03-31")
    b = fin.budget_status(ds.budgets, ds.cats, spend, "2026-03-01", date(2026, 3, 10))[0]
    assert b["pct"] == pytest.approx(92) and b["crossed"] == [75, 90] and b["level"] == "high"
    assert b["remaining"] == 400 and b["projected"] == pytest.approx(4600 / 10 * 31)
    past = fin.budget_status(ds.budgets, ds.cats, spend, "2026-03-01", date(2026, 5, 1))[0]
    assert past["projected"] == 4600                                   # finished months aren't extrapolated


def test_goal_required_monthly_no_returns():
    g = {"id": "g", "goal_name": "Car", "goal_type": "car", "target_amount": 600000, "current_allocated_amount": 60000,
         "target_date": "2028-03-01", "priority": "high", "inflation_assumption": 0, "status": "active"}
    m = fin.goal_metrics(g, 40000, date(2026, 3, 1))
    assert m["months_left"] == 24 and m["remaining"] == 500000
    assert m["required_monthly"] == pytest.approx(500000 / 24)
    assert m["pct"] == pytest.approx(100000 / 600000 * 100)


def test_goal_inflation_adjusted_target():
    assert fin.inflate(1_000_000, 6, 3) == pytest.approx(1_191_016)
    g = {"id": "g", "goal_name": "House", "goal_type": "house", "target_amount": 1_000_000, "current_allocated_amount": 0,
         "target_date": "2029-03-01", "priority": "medium", "inflation_assumption": 6, "status": "active"}
    m = fin.goal_metrics(g, 0, date(2026, 3, 1))
    assert m["adjusted_target"] == pytest.approx(1_000_000 * 1.06 ** (1096 / 365.25), rel=1e-6)


def test_goal_past_due_and_completed():
    g = {"id": "g", "goal_name": "Trip", "goal_type": "travel", "target_amount": 1000, "current_allocated_amount": 0,
         "target_date": "2026-01-01", "priority": "low", "inflation_assumption": 0, "status": "active"}
    assert fin.goal_metrics(g, 0, date(2026, 3, 1))["required_monthly"] == 1000       # due now
    assert fin.goal_metrics(g, 1500, date(2026, 3, 1))["remaining"] == 0


def test_feasibility_commits_surplus_by_priority():
    base = dict(status="active", remaining=1, target_date=date(2027, 1, 1))
    ms = [dict(base, id="a", priority="low", required_monthly=5000), dict(base, id="b", priority="high", required_monthly=8000)]
    out = {g["id"]: g for g in fin.goal_feasibility(ms, 10000)}
    assert out["b"]["state"] == "affordable" and out["a"]["state"] == "partial" and out["a"]["shortfall"] == 3000
    assert {g["id"]: g["state"] for g in fin.goal_feasibility(ms, 0)} == {"a": "unfunded", "b": "unfunded"}


def test_compound_growth_and_required_contribution():
    assert fin.future_value(0, 1000, 0, 1) == 12000
    assert fin.future_value(10000, 0, 12, 1) == pytest.approx(10000 * (1.01) ** 12)
    fv = fin.future_value(0, 5000, 12, 10)
    assert fv == pytest.approx(5000 * ((1.01 ** 120 - 1) / 0.01))
    need = fin.required_monthly(fv, 120, 12)
    assert need == pytest.approx(5000, rel=1e-9)
    assert fin.future_value(0, 5000, 12, 10, fee_pct=2) < fv            # fees reduce growth
    assert fin.required_monthly(1200, 12) == 100


def test_net_worth_and_timeline():
    al = pd.DataFrame([
        {"id": "1", "record_type": "asset", "name": "FD", "category": "Fixed deposit", "current_value": 100000, "valuation_date": "2026-01-01", "created_at": "1"},
        {"id": "2", "record_type": "asset", "name": "FD", "category": "Fixed deposit", "current_value": 110000, "valuation_date": "2026-03-01", "created_at": "2"},
        {"id": "3", "record_type": "liability", "name": "Loan", "category": "Education loan", "current_value": 40000, "valuation_date": "2026-02-01", "created_at": "3"}])
    nw = fin.net_worth(al, None)
    assert nw == {**nw, "assets": 110000, "liabilities": 40000, "net_worth": 70000}
    tl = fin.net_worth_timeline(al)
    assert list(tl["net_worth"]) == [100000, 60000, 70000]


def test_emergency_target():
    assert fin.emergency_target(25000, 6) == 150000


def test_unusual_and_recurring_detection():
    r = seeded_repo()
    demo_history(r, date(2026, 6, 28), months=5)
    ds = dataset(r)
    rec = fin.recurring_expenses(ds.tx)
    assert {"Rent", "Netflix"} <= set(rec["description"])
    assert "Dinner out" not in set(rec["description"])                  # one spiky month breaks the "similar amounts" rule


def test_unusual_months_flags_only_the_outlier():
    idx = pd.date_range("2026-01-01", periods=6, freq="MS")
    s = pd.DataFrame({"consumption": [20000, 21000, 19500, 20500, 20200, 45000]}, index=idx)
    assert list(fin.unusual_months(s).index) == [idx[-1]]
    assert fin.unusual_months(s.head(3)).empty                          # needs 4+ months


def test_months_until_calendar_math():
    assert fin.months_until(date(2028, 3, 1), date(2026, 3, 1)) == 24
    assert fin.months_until(date(2026, 3, 15), date(2026, 3, 1)) == 1
    assert fin.months_until(date(2026, 5, 31), date(2026, 3, 31)) == 2
    assert fin.months_until(date(2026, 1, 1), date(2026, 3, 1)) == 0


def test_insights_cite_period_and_figures():
    r = seeded_repo()
    demo_history(r, date(2026, 6, 28), months=4)
    ds = dataset(r)
    ins = fin.generate_insights(ds.tx, ds.summary, "2026-05-01", {"savings": 20, "wants": 30}, lambda v: f"₹{v:,.0f}")
    text = " ".join(i["detail"] + i["title"] for i in ins)
    assert "May 2026" in text and "₹" in text
    assert any("Restaurants" in i["title"] for i in ins)               # the April spike
    assert fin.generate_insights(ds.tx.iloc[0:0], ds.summary.iloc[0:0], "2026-05-01", {}, str) == []
