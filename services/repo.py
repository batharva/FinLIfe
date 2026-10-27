"""Database service layer. All reads/writes go through Repo, which is bound to ONE authenticated user.

Ownership is enforced three times:
  1. Repo forces user_id = authenticated user on every insert and filters every update/delete by it.
  2. The Supabase client sends the user's JWT, so PostgreSQL Row Level Security applies.
  3. Composite foreign keys (id, user_id) stop rows from referencing another user's records.
"""
from __future__ import annotations

import logging
from datetime import date

import httpx
from postgrest.exceptions import APIError

from utils.defaults import DEFAULT_ACCOUNTS, DEFAULT_CATEGORIES

log = logging.getLogger("finlife.repo")

TABLES = ("accounts", "categories", "transactions", "budgets", "financial_goals", "goal_contributions",
          "investment_plans", "assets_and_liabilities", "recurring_transactions")
PAGE = 1000


class DataError(Exception):
    """A database problem with a message that is safe to show to the user."""


class SessionExpired(DataError):
    pass


def _friendly(e: Exception) -> DataError:
    if isinstance(e, APIError):
        code, msg = str(getattr(e, "code", "")), str(getattr(e, "message", e))
        if "JWT" in msg or code in ("PGRST301", "PGRST303"):
            return SessionExpired("Your session expired. Please sign in again.")
        if code == "23505":
            return DataError("That record already exists.")
        if code == "23503":
            return DataError("This record is linked to other data (or points to something that no longer exists).")
        if code in ("23514", "22003", "22P02", "22007"):
            return DataError("One of the values is outside the allowed range or format.")
        if code in ("42501",):
            return DataError("You don't have permission to change that record.")
        log.error("database error %s: %s", code, msg)
        return DataError("The database rejected that request. Please check your input and try again.")
    if isinstance(e, httpx.TimeoutException):
        return DataError("The database took too long to respond. Nothing was lost - please try again.")
    if isinstance(e, httpx.HTTPError):
        return DataError("Couldn't reach the database. Check your connection and try again.")
    log.exception("unexpected data error")
    return DataError("Something went wrong while saving. Your data was not changed.")


class Repo:
    def __init__(self, client, user_id: str):
        if not user_id:
            raise ValueError("Repo requires an authenticated user id")
        self._c, self.user_id = client, str(user_id)

    # -- generic CRUD ---------------------------------------------------
    def select(self, table: str, order: str = "id") -> list[dict]:
        self._check(table)
        rows, offset = [], 0
        try:
            while True:
                q = self._c.table(table).select("*").order(order)
                if table != "profiles":
                    q = q.eq("user_id", self.user_id)
                data = q.range(offset, offset + PAGE - 1).execute().data or []
                rows += data
                if len(data) < PAGE:
                    return rows
                offset += PAGE
        except Exception as e:
            raise _friendly(e) from e

    def insert(self, table: str, rows: dict | list[dict]) -> list[dict]:
        self._check(table)
        batch = [rows] if isinstance(rows, dict) else rows
        if not batch:
            return []
        payload = [{**r, "user_id": self.user_id} for r in batch]     # client-supplied user_id is overwritten
        try:
            return self._c.table(table).insert(payload).execute().data or []
        except Exception as e:
            raise _friendly(e) from e

    def update(self, table: str, row_id: str, values: dict) -> list[dict]:
        self._check(table)
        vals = {k: v for k, v in values.items() if k not in ("id", "user_id", "created_at")}
        try:
            return self._c.table(table).update(vals).eq("id", row_id).eq("user_id", self.user_id).execute().data or []
        except Exception as e:
            raise _friendly(e) from e

    def delete(self, table: str, row_id: str) -> None:
        self._check(table)
        try:
            self._c.table(table).delete().eq("id", row_id).eq("user_id", self.user_id).execute()
        except Exception as e:
            raise _friendly(e) from e

    def delete_where(self, table: str, column: str, value: str) -> None:
        self._check(table)
        try:
            self._c.table(table).delete().eq(column, value).eq("user_id", self.user_id).execute()
        except Exception as e:
            raise _friendly(e) from e

    # -- profile ----------------------------------------------------------
    def get_profile(self, fallback_name: str = "") -> dict:
        try:
            rows = self._c.table("profiles").select("*").eq("id", self.user_id).execute().data
            if rows:
                return rows[0]
            return self._c.table("profiles").insert({"id": self.user_id, "full_name": fallback_name}).execute().data[0]
        except Exception as e:
            raise _friendly(e) from e

    def update_profile(self, values: dict) -> None:
        vals = {k: v for k, v in values.items() if k not in ("id", "created_at")}
        try:
            self._c.table("profiles").update(vals).eq("id", self.user_id).execute()
        except Exception as e:
            raise _friendly(e) from e

    # -- domain helpers -----------------------------------------------------
    def add_transfer(self, from_account: str, to_account: str, amount: float, on: date, description: str,
                     payment_method: str = "Bank transfer", notes: str | None = None) -> None:
        """Two linked rows inserted in ONE statement (atomic). Neutral for income/expense reports."""
        import uuid
        gid = str(uuid.uuid4())
        base = {"amount": round(amount, 2), "transaction_date": on.isoformat(), "description": description,
                "payment_method": payment_method, "notes": notes, "transfer_group_id": gid, "category_id": None}
        self.insert("transactions", [{**base, "account_id": from_account, "transaction_type": "transfer_out"},
                                     {**base, "account_id": to_account, "transaction_type": "transfer_in"}])

    def delete_transaction(self, tx_id: str, transfer_group_id: str | None = None) -> None:
        if transfer_group_id:
            self.delete_where("transactions", "transfer_group_id", transfer_group_id)   # remove both legs
        else:
            self.delete("transactions", tx_id)

    def seed_defaults(self) -> None:
        """Idempotent: creates only the default accounts/categories that are missing."""
        have_acc = {a["account_name"].lower() for a in self.select("accounts")}
        self.insert("accounts", [a for a in DEFAULT_ACCOUNTS if a["account_name"].lower() not in have_acc])
        have_cat = {c["name"].lower() for c in self.select("categories") if not c.get("parent_category_id")}
        self.insert("categories", [c for c in DEFAULT_CATEGORIES if c["name"].lower() not in have_cat])
        self.update_profile({"seeded": True})

    @staticmethod
    def _check(table: str):
        if table not in TABLES:
            raise ValueError(f"unknown table {table}")


def build_repo(access_token: str, user_id: str) -> Repo:
    """A Supabase client that sends THIS user's JWT, so Row Level Security applies to every call."""
    from supabase import ClientOptions, create_client
    from supabase_auth import SyncMemoryStorage

    from services import config
    client = create_client(
        config.get("SUPABASE_URL"), config.get("SUPABASE_ANON_KEY"),
        options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"}, auto_refresh_token=False,
                              persist_session=False, storage=SyncMemoryStorage()))
    return Repo(client, user_id)
