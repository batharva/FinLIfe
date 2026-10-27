"""Loads one user's data (cached per user + data version) and shapes it into DataFrames."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from services import finance as fin
from services.repo import TABLES, Repo


@st.cache_data(ttl=300, show_spinner=False, max_entries=64)
def _load_raw(user_id: str, version: int, _repo: Repo) -> dict:
    """Cache key = (user_id, version). `_repo` is excluded from hashing, so data can never be shared across users."""
    return {t: _repo.select(t) for t in TABLES}


@dataclass
class Dataset:
    tx: pd.DataFrame
    cats: pd.DataFrame
    accounts: pd.DataFrame
    budgets: pd.DataFrame
    goals: pd.DataFrame
    contribs: pd.DataFrame
    plans: pd.DataFrame
    al: pd.DataFrame
    recurring: pd.DataFrame

    @property
    def summary(self) -> pd.DataFrame:
        return fin.monthly_summary(self.tx)


def build_dataset(raw: dict) -> Dataset:
    cats = fin.to_df(raw["categories"], fin.CAT_COLUMNS)
    tx = fin.enrich(fin.to_tx_df(raw["transactions"]), cats)
    acc_cols = ["id", "account_name", "account_type", "opening_balance", "currency"]
    accounts = fin.account_balances(fin.to_df(raw["accounts"], acc_cols), tx)
    return Dataset(
        tx=tx, cats=cats, accounts=accounts,
        budgets=fin.to_df(raw["budgets"], ["id", "category_id", "period", "budget_amount", "warning_thresholds"]),
        goals=fin.to_df(raw["financial_goals"], ["id", "goal_name", "goal_type", "target_amount", "current_allocated_amount",
                                                 "target_date", "priority", "inflation_assumption", "status", "notes"]),
        contribs=fin.to_df(raw["goal_contributions"], ["id", "goal_id", "amount", "contribution_date", "source", "notes"]),
        plans=fin.to_df(raw["investment_plans"], ["id", "goal_id", "plan_name", "initial_amount", "monthly_contribution",
                                                  "investment_horizon", "risk_profile", "return_assumption", "low_return",
                                                  "high_return", "fee_assumption", "created_at"]),
        al=fin.to_df(raw["assets_and_liabilities"], ["id", "record_type", "name", "category", "current_value",
                                                     "valuation_date", "notes", "created_at"]),
        recurring=fin.to_df(raw["recurring_transactions"], ["id", "description", "transaction_type", "amount", "category_id",
                                                            "account_id", "payment_method", "frequency", "next_due_date",
                                                            "is_active"]),
    )


def bump_version() -> None:
    st.session_state["_v"] = st.session_state.get("_v", 0) + 1


def load(repo: Repo) -> Dataset:
    return build_dataset(_load_raw(repo.user_id, st.session_state.get("_v", 0), repo))
