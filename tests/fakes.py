"""In-memory stand-ins so tests never need Supabase credentials."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from services.repo import DataError, Repo, TABLES
from utils.defaults import DEFAULT_ACCOUNTS, DEFAULT_CATEGORIES


class FakeRepo(Repo):
    """Same public interface and ownership rules as Repo, backed by dicts."""
    def __init__(self, user_id="user-a", store=None):
        self.user_id = user_id
        self.store = store if store is not None else {t: [] for t in TABLES}
        self.profiles = {}

    def select(self, table, order="id"):
        self._check(table)
        return [dict(r) for r in self.store[table] if r["user_id"] == self.user_id]

    def insert(self, table, rows):
        self._check(table)
        out = []
        for r in ([rows] if isinstance(rows, dict) else rows):
            row = {"id": str(uuid.uuid4()), "created_at": "2026-01-01T00:00:00", **r, "user_id": self.user_id}
            if table == "transactions" and row["amount"] <= 0:
                raise DataError("One of the values is outside the allowed range or format.")
            self.store[table].append(row)
            out.append(dict(row))
        return out

    def update(self, table, row_id, values):
        self._check(table)
        for r in self.store[table]:
            if r["id"] == row_id and r["user_id"] == self.user_id:
                r.update({k: v for k, v in values.items() if k not in ("id", "user_id")})
                return [dict(r)]
        return []

    def delete(self, table, row_id):
        self.store[table] = [r for r in self.store[table] if not (r["id"] == row_id and r["user_id"] == self.user_id)]

    def delete_where(self, table, column, value):
        self.store[table] = [r for r in self.store[table] if not (r.get(column) == value and r["user_id"] == self.user_id)]

    def get_profile(self, fallback_name=""):
        return self.profiles.setdefault(self.user_id, {"id": self.user_id, "full_name": fallback_name or "Test User", "preferred_currency": "INR",
                                                       "preferred_theme": "system", "alloc_needs": 50, "alloc_wants": 30, "alloc_savings": 20, "seeded": False})

    def update_profile(self, values):
        self.get_profile().update(values)


def seeded_repo(user_id="user-a", store=None) -> FakeRepo:
    r = FakeRepo(user_id, store)
    r.get_profile()
    r.seed_defaults()
    return r


def cat_id(repo, name):
    return next(c["id"] for c in repo.select("categories") if c["name"] == name)


def acct_id(repo, name="Bank account"):
    return next(a["id"] for a in repo.select("accounts") if a["account_name"] == name)


def demo_history(repo, today: date | None = None, months: int = 4) -> None:
    """Salary + typical spending for the last N months (test/screenshot data only - never loaded by the real app)."""
    today = today or date.today()
    bank = acct_id(repo)
    rows = []
    for i in range(months, -1, -1):
        y, mth = divmod(today.year * 12 + today.month - 1 - i, 12)
        d0 = date(y, mth + 1, 1)
        def add(day, t, amt, desc, cat):
            dd = min(d0 + timedelta(days=day - 1), today)
            rows.append({"account_id": bank, "category_id": cat_id(repo, cat), "transaction_type": t, "description": desc, "amount": amt,
                         "transaction_date": dd.isoformat(), "payment_method": "UPI", "notes": None})
        add(1, "income", 60000, "Salary", "Salary")
        add(2, "expense", 15000, "Rent", "Rent or hostel")
        add(5, "expense", 6000 + 500 * i, "Groceries", "Groceries")
        add(8, "expense", 1200, "Electricity", "Utilities")
        add(10, "expense", 649, "Netflix", "Nonessential subscriptions")
        add(12, "expense", 2500 + (3500 if i == 1 else 0), "Dinner out", "Restaurants and cafés")
        add(15, "expense", 4000, "Shopping", "Shopping")
        add(20, "investment", 8000, "SIP", "Mutual funds")
    repo.insert("transactions", rows)
