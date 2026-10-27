"""CSV export / import for transactions (pure functions; no database access)."""
from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass, field

import pandas as pd

EXPORT_COLUMNS = ["date", "type", "amount", "description", "category", "subcategory", "account",
                  "payment_method", "notes"]
TYPE_ALIASES = {"income": "income", "credit": "income", "expense": "expense", "debit": "expense",
                "investment": "investment", "invest": "investment", "refund": "refund",
                "reimbursement": "refund"}
PAYMENT_METHODS = ["UPI", "Cash", "Debit card", "Credit card", "Bank transfer", "Other"]
MAX_ROWS, MAX_BYTES = 5000, 2_000_000


def safe_cell(v) -> str:
    """Neutralise spreadsheet formula injection (=, +, -, @ at the start of a cell)."""
    s = "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def export_transactions(df: pd.DataFrame, accounts: pd.DataFrame) -> bytes:
    names = accounts.set_index("id")["account_name"] if len(accounts) else pd.Series(dtype=object)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(EXPORT_COLUMNS)
    for _, r in df.sort_values("transaction_date").iterrows():
        w.writerow([r["transaction_date"].strftime("%Y-%m-%d"), r["transaction_type"], f"{r['amount']:.2f}",
                    safe_cell(r["description"]), safe_cell(r.get("category", "")), safe_cell(r.get("subcategory", "")),
                    safe_cell(names.get(r["account_id"], "")), r["payment_method"], safe_cell(r["notes"])])
    return buf.getvalue().encode("utf-8-sig")


@dataclass
class ImportPlan:
    rows: list[dict] = field(default_factory=list)          # ready to insert (category resolved by name later)
    duplicates: int = 0
    errors: list[str] = field(default_factory=list)
    new_categories: dict[str, str] = field(default_factory=dict)   # name -> classification to create


def _num(s: str) -> float:
    s = str(s).replace("₹", "").replace("$", "").replace(",", "").strip()
    return float(s)


def _key(date, ttype, amount, desc, account_id):
    return (str(date)[:10], ttype, round(float(amount), 2), (desc or "").strip().lower(), account_id)


def parse_import(content: bytes, cats: pd.DataFrame, accounts: pd.DataFrame, default_account_id: str,
                 existing: pd.DataFrame) -> ImportPlan:
    plan = ImportPlan()
    if len(content) > MAX_BYTES:
        plan.errors.append("File is larger than 2 MB. Split it into smaller files.")
        return plan
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        plan.errors.append("File is not UTF-8 text. Export it from your spreadsheet as 'CSV UTF-8'.")
        return plan
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        plan.errors.append("The file is empty.")
        return plan
    reader.fieldnames = [h.strip().lower().replace(" ", "_") for h in reader.fieldnames]
    missing = [c for c in ("date", "type", "amount") if c not in reader.fieldnames]
    if missing:
        plan.errors.append(f"Missing required column(s): {', '.join(missing)}. Expected: {', '.join(EXPORT_COLUMNS)}.")
        return plan

    cat_by_name = {str(r["name"]).lower(): r for _, r in cats.iterrows()} if len(cats) else {}
    acc_by_name = {str(r["account_name"]).lower(): r["id"] for _, r in accounts.iterrows()} if len(accounts) else {}
    seen = Counter()
    if len(existing):
        for _, r in existing.iterrows():
            seen[_key(r["transaction_date"], r["transaction_type"], r["amount"], r["description"], r["account_id"])] += 1

    for i, row in enumerate(reader, start=2):
        if len(plan.rows) + plan.duplicates >= MAX_ROWS:
            plan.errors.append(f"Stopped at {MAX_ROWS} rows; import the remainder in a second file.")
            break
        try:
            ttype = TYPE_ALIASES.get((row.get("type") or "").strip().lower())
            if ttype is None:
                raise ValueError(f"unknown type '{row.get('type')}' (use income, expense, investment or refund)")
            d = pd.to_datetime((row.get("date") or "").strip(), dayfirst=True, errors="coerce")
            if pd.isna(d):
                raise ValueError(f"unreadable date '{row.get('date')}'")
            amount = _num(row.get("amount") or "")
            if not amount > 0:
                raise ValueError("amount must be greater than zero")
            acc_name = (row.get("account") or "").strip().lower()
            if acc_name and acc_name not in acc_by_name:
                raise ValueError(f"unknown account '{row.get('account')}'")
            account_id = acc_by_name.get(acc_name, default_account_id)
            desc = (row.get("description") or "").strip()[:200]
            pay = (row.get("payment_method") or "Other").strip()
            pay = next((p for p in PAYMENT_METHODS if p.lower() == pay.lower()), "Other")
            cat_name = (row.get("subcategory") or "").strip() or (row.get("category") or "").strip()
            if cat_name and cat_name.lower() not in cat_by_name and cat_name not in plan.new_categories:
                plan.new_categories[cat_name] = {"income": "income", "investment": "investment"}.get(ttype, "want")
        except ValueError as e:
            plan.errors.append(f"Row {i}: {e}")
            continue
        k = _key(d.date(), ttype, amount, desc, account_id)
        if seen[k] > 0:
            seen[k] -= 1
            plan.duplicates += 1
            continue
        plan.rows.append({"transaction_date": d.date().isoformat(), "transaction_type": ttype, "amount": round(amount, 2),
                          "description": desc, "category_name": cat_name, "account_id": account_id,
                          "payment_method": pay, "notes": (row.get("notes") or "").strip()[:500] or None})
    return plan
