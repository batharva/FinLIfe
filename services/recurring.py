"""Posting due recurring templates as real transactions."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from services.finance import add_months

MAX_CATCHUP = 24


def next_date(d: date, frequency: str) -> date:
    return {"weekly": lambda: d + timedelta(days=7), "monthly": lambda: add_months(d, 1),
            "quarterly": lambda: add_months(d, 3), "yearly": lambda: add_months(d, 12)}[frequency]()


def due_rows(recurring: pd.DataFrame, today: date) -> tuple[list[dict], list[tuple[str, date]]]:
    """Returns (transactions to insert, [(template_id, new_next_due_date)])."""
    rows, updates = [], []
    for _, r in recurring.iterrows():
        if not r["is_active"]:
            continue
        due, n = pd.Timestamp(r["next_due_date"]).date(), 0
        while due <= today and n < MAX_CATCHUP:
            rows.append({"account_id": r["account_id"], "category_id": r["category_id"] if pd.notna(r["category_id"]) else None,
                         "transaction_type": r["transaction_type"], "description": r["description"], "amount": float(r["amount"]),
                         "transaction_date": due.isoformat(), "payment_method": r["payment_method"] or "Other",
                         "notes": "Posted from recurring template"})
            due, n = next_date(due, r["frequency"]), n + 1
        if n:
            updates.append((r["id"], due))
    return rows, updates


def post_due(repo, recurring: pd.DataFrame, today: date) -> int:
    rows, updates = due_rows(recurring, today)
    if not rows:
        return 0
    repo.insert("transactions", rows)                 # one statement: all-or-nothing
    for tid, nxt in updates:
        repo.update("recurring_transactions", tid, {"next_due_date": nxt.isoformat()})
    return len(rows)
