from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

import pandas as pd
import streamlit as st

from services.auth import AuthSession
from services.data import Dataset
from services.repo import Repo
from utils.format import money

CLASS_FOR_TYPE = {"income": {"income"}, "expense": {"need", "want"}, "investment": {"saving", "investment"},
                  "refund": {"need", "want"}}
TYPE_LABELS = {"income": "Income", "expense": "Expense", "investment": "Savings & investment", "refund": "Refund",
               "transfer": "Transfer / card bill payment"}


@dataclass
class Ctx:
    repo: Repo
    ds: Dataset
    profile: dict
    session: AuthSession
    month: pd.Timestamp
    today: date
    navigate: Callable[[str], None]

    @property
    def cur(self) -> str:
        return self.profile.get("preferred_currency", "INR")

    def m(self, v, decimals: int = 0) -> str:
        return money(v, self.cur, decimals)

    @property
    def targets(self) -> dict:
        p = self.profile
        return {"needs": float(p.get("alloc_needs", 50)), "wants": float(p.get("alloc_wants", 30)),
                "savings": float(p.get("alloc_savings", 20))}


def category_choices(cats: pd.DataFrame, classes: set[str]) -> dict[str, str]:
    """{category_id: label}; sub-categories appear as 'Parent › Child' so a single select covers both levels."""
    if cats.empty:
        return {}
    names = cats.set_index("id")["name"]
    out = {}
    top = cats[cats["parent_category_id"].isna() & cats["financial_classification"].isin(classes)].sort_values("name")
    for _, r in top.iterrows():
        out[r["id"]] = r["name"]
        for _, c in cats[cats["parent_category_id"] == r["id"]].sort_values("name").iterrows():
            out[c["id"]] = f"{r['name']} › {c['name']}"
    return out


def account_choices(accounts: pd.DataFrame) -> dict[str, str]:
    return {r["id"]: r["account_name"] for _, r in accounts.sort_values("account_name").iterrows()} if len(accounts) else {}


def to_date(x) -> date:
    return pd.Timestamp(x).date()


def clean(v):
    """NaN/NaT -> None so values can be sent to the database."""
    return None if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)) else v
