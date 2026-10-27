"""Pure financial calculations. No Streamlit, no database - fully unit-testable.

Accounting model
----------------
transaction_type        effect on account balance   counts as
income                  +                           income
refund                  +                           reduces consumption (reimbursements too)
expense                 -                           consumption (credit-card purchases count when made)
investment              -                           allocation of funds, NOT consumption
transfer_out/_in        - / +                       neutral (also used for credit-card bill payments:
                                                    bank -> card account settles the liability)
"""
from __future__ import annotations

import calendar
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

SIGN = {"income": 1, "refund": 1, "transfer_in": 1, "expense": -1, "investment": -1, "transfer_out": -1}
TX_COLUMNS = ["id", "account_id", "category_id", "transaction_type", "description", "amount",
              "transaction_date", "payment_method", "notes", "is_essential", "transfer_group_id"]
CAT_COLUMNS = ["id", "name", "parent_category_id", "financial_classification", "is_essential", "is_default"]
SUMMARY_COLUMNS = ["income", "consumption", "investment", "savings", "net_cash_flow",
                   "savings_rate", "needs", "wants", "unclassified"]
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


# ------------------------------------------------------------------ frames
def to_df(rows, columns) -> pd.DataFrame:
    return pd.DataFrame(rows or [], columns=columns) if rows else pd.DataFrame(columns=columns)


def to_tx_df(rows) -> pd.DataFrame:
    df = to_df(rows, TX_COLUMNS)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0).astype(float)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


def enrich(tx: pd.DataFrame, cats: pd.DataFrame) -> pd.DataFrame:
    """Add category / subcategory / classification / signed effect columns."""
    df = tx.copy()
    c = cats.set_index("id") if len(cats) else pd.DataFrame(
        columns=CAT_COLUMNS[1:], index=pd.Index([], name="id"))
    df["cat_name"] = df["category_id"].map(c["name"])
    parent = df["category_id"].map(c["parent_category_id"])
    df["root_id"] = parent.where(parent.notna(), df["category_id"])
    df["category"] = df["root_id"].map(c["name"]).fillna("Uncategorised")
    df["subcategory"] = df["cat_name"].where(parent.notna(), "").fillna("")
    df["classification"] = df["category_id"].map(c["financial_classification"])
    spend = df["transaction_type"].isin(["expense", "refund"])
    df.loc[spend & df["is_essential"].eq(True), "classification"] = "need"
    df.loc[spend & df["is_essential"].eq(False), "classification"] = "want"
    df.loc[spend & df["classification"].isna(), "classification"] = "unclassified"
    df["effect"] = df["transaction_type"].map(SIGN).fillna(0) * df["amount"]
    df["net_spend"] = np.where(df["transaction_type"] == "expense", df["amount"],
                               np.where(df["transaction_type"] == "refund", -df["amount"], 0.0))
    return df


# ------------------------------------------------------------------ dates
def month_start(d) -> pd.Timestamp:
    return pd.Timestamp(d).to_period("M").to_timestamp()


def month_end(d) -> pd.Timestamp:
    return month_start(d) + pd.offsets.MonthEnd(0)


def months_until(target: date, today: date) -> int:
    """Calendar months (rounded up) from today to the target date; 0 if already due."""
    if target <= today:
        return 0
    m = (target.year - today.year) * 12 + target.month - today.month
    if target.day < today.day:
        m -= 1
    return m + (1 if add_months(today, m) < target else 0)


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


# ------------------------------------------------------------------ summaries
def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per calendar month between first and last transaction (empty months = 0)."""
    if df.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS, index=pd.DatetimeIndex([], name="month"))
    d = df.assign(month=df["transaction_date"].dt.to_period("M").dt.to_timestamp())
    pv = d.pivot_table(index="month", columns="transaction_type", values="amount", aggfunc="sum", fill_value=0.0)
    for t in SIGN:
        if t not in pv:
            pv[t] = 0.0
    out = pd.DataFrame(index=pv.index)
    out["income"] = pv["income"]
    out["consumption"] = pv["expense"] - pv["refund"]
    out["investment"] = pv["investment"]
    out["savings"] = out["income"] - out["consumption"]            # includes money invested
    out["net_cash_flow"] = out["savings"] - out["investment"]      # what stays in accounts
    out["savings_rate"] = np.where(out["income"] > 0, out["savings"] / out["income"].replace(0, np.nan) * 100, np.nan)
    cls = d.pivot_table(index="month", columns="classification", values="net_spend", aggfunc="sum", fill_value=0.0)
    for k in ("need", "want", "unclassified"):
        if k not in cls:
            cls[k] = 0.0
    out["needs"], out["wants"], out["unclassified"] = cls["need"], cls["want"], cls["unclassified"]
    full = pd.date_range(out.index.min(), out.index.max(), freq="MS", name="month")
    out = out.reindex(full)
    for col in SUMMARY_COLUMNS:
        if col != "savings_rate":
            out[col] = out[col].fillna(0.0)
    out["savings_rate"] = np.where(out["income"] > 0, out["savings"] / out["income"].replace(0, np.nan) * 100, np.nan)
    return out[SUMMARY_COLUMNS]


def month_metrics(summary: pd.DataFrame, month) -> dict:
    ms = month_start(month)
    zero = {c: 0.0 for c in SUMMARY_COLUMNS}
    zero["savings_rate"] = float("nan")
    cur = summary.loc[ms].to_dict() if ms in summary.index else dict(zero)
    prev_ms = ms - pd.offsets.MonthBegin(1)
    prev = summary.loc[prev_ms].to_dict() if prev_ms in summary.index else None
    return {"current": cur, "previous": prev}


def average_monthly(summary: pd.DataFrame, n: int = 3, today: date | None = None) -> tuple[pd.Series, int]:
    """Mean of the last n COMPLETE months; falls back to all months when none are complete."""
    if summary.empty:
        return pd.Series({c: 0.0 for c in SUMMARY_COLUMNS}), 0
    cur = month_start(today or date.today())
    complete = summary[summary.index < cur].tail(n)
    use = complete if len(complete) else summary
    return use.mean(numeric_only=True), len(use)


def distinct_months(df: pd.DataFrame) -> int:
    return 0 if df.empty else int(df["transaction_date"].dt.to_period("M").nunique())


def account_balances(accounts: pd.DataFrame, tx: pd.DataFrame) -> pd.DataFrame:
    acc = accounts.copy()
    if acc.empty:
        acc["balance"] = []
        return acc
    acc["opening_balance"] = pd.to_numeric(acc["opening_balance"]).astype(float)
    eff = tx.groupby("account_id")["effect"].sum() if len(tx) else pd.Series(dtype=float)
    acc["balance"] = acc["opening_balance"] + acc["id"].map(eff).fillna(0.0)
    return acc


def category_spend(df: pd.DataFrame, start, end) -> pd.DataFrame:
    """Net consumption (expenses - refunds) per root category in [start, end]."""
    m = df[(df["transaction_date"] >= pd.Timestamp(start)) & (df["transaction_date"] <= pd.Timestamp(end))
           & df["transaction_type"].isin(["expense", "refund"])]
    if m.empty:
        return pd.DataFrame(columns=["category", "root_id", "classification", "amount"])
    g = m.groupby(["category", "root_id", "classification"], dropna=False)["net_spend"].sum().reset_index()
    g = g.rename(columns={"net_spend": "amount"})
    return g[g["amount"] > 0].sort_values("amount", ascending=False).reset_index(drop=True)


def allocation(summary_row: dict) -> dict:
    income = float(summary_row.get("income", 0) or 0)
    needs, wants = float(summary_row.get("needs", 0)), float(summary_row.get("wants", 0))
    unc = float(summary_row.get("unclassified", 0))
    savings = max(income - needs - wants - unc, 0.0)
    return {"Needs": max(needs, 0), "Wants": max(wants, 0), "Unclassified": max(unc, 0), "Savings": savings,
            "overspent": income - needs - wants - unc < 0 and income > 0}


# ------------------------------------------------------------------ budgets
def projected_month_end(spent: float, month, today: date) -> float:
    ms, me = month_start(month), month_end(month)
    t = pd.Timestamp(today)
    if t < ms or t > me:
        return spent
    return spent / t.day * me.day


def budget_status(budgets: pd.DataFrame, cats: pd.DataFrame, spend: pd.DataFrame, month, today: date) -> list[dict]:
    names = cats.set_index("id")["name"] if len(cats) else pd.Series(dtype=object)
    spent_by = spend.groupby("root_id")["amount"].sum() if len(spend) else pd.Series(dtype=float)
    out = []
    for _, b in budgets.iterrows():
        limit = float(b["budget_amount"])
        spent = float(spent_by.get(b["category_id"], 0.0))
        thresholds = sorted(int(x) for x in (b.get("warning_thresholds") or [75, 90, 100]))
        pct = spent / limit * 100 if limit else 0.0
        crossed = [t for t in thresholds if pct >= t]
        level = "ok" if not crossed else ("over" if crossed[-1] >= 100 else "high" if crossed[-1] >= 90 else "warn")
        out.append({"budget_id": b["id"], "category_id": b["category_id"], "category": names.get(b["category_id"], "?"),
                    "limit": limit, "spent": spent, "remaining": limit - spent, "pct": pct,
                    "projected": projected_month_end(spent, month, today), "crossed": crossed, "level": level})
    return sorted(out, key=lambda r: -r["pct"])


# ------------------------------------------------------------------ goals
def inflate(amount: float, pct: float, years: float) -> float:
    return amount * (1 + pct / 100) ** max(years, 0)


def future_value(initial: float, monthly: float, annual_return_pct: float, years: float, fee_pct: float = 0.0) -> float:
    n = int(round(years * 12))
    r = (annual_return_pct - fee_pct) / 100 / 12
    if n <= 0:
        return float(initial)
    if abs(r) < 1e-12:
        return float(initial + monthly * n)
    g = (1 + r) ** n
    return float(initial * g + monthly * (g - 1) / r)


def growth_series(initial, monthly, annual_return_pct, years, fee_pct=0.0) -> pd.DataFrame:
    n = int(round(years * 12))
    rows = [(m, future_value(initial, monthly, annual_return_pct, m / 12, fee_pct), initial + monthly * m) for m in range(n + 1)]
    return pd.DataFrame(rows, columns=["month", "value", "invested"])


def required_monthly(target: float, months: int, annual_return_pct: float = 0.0, initial: float = 0.0,
                     fee_pct: float = 0.0) -> float:
    """Monthly contribution needed so that initial + contributions (growing) reach `target`."""
    if months <= 0:
        return max(target - initial, 0.0)
    r = (annual_return_pct - fee_pct) / 100 / 12
    if abs(r) < 1e-12:
        return max(target - initial, 0.0) / months
    g = (1 + r) ** months
    return max((target - initial * g) * r / (g - 1), 0.0)


def goal_metrics(goal: dict, contributed: float, today: date, recent_monthly_rate: float = 0.0) -> dict:
    target_date = pd.Timestamp(goal["target_date"]).date()
    months_left = months_until(target_date, today)
    years = max((target_date - today).days, 0) / 365.25
    base = float(goal["target_amount"])
    infl = float(goal.get("inflation_assumption") or 0)
    adjusted = inflate(base, infl, years)
    allocated = float(goal.get("current_allocated_amount") or 0) + float(contributed)
    remaining = max(adjusted - allocated, 0.0)
    required = remaining / months_left if months_left > 0 else remaining   # no-return formula
    est = None
    if remaining <= 0:
        est = today
    elif recent_monthly_rate > 0:
        est = add_months(today, math.ceil(remaining / recent_monthly_rate))
    return {"id": goal["id"], "name": goal["goal_name"], "type": goal["goal_type"], "priority": goal["priority"],
            "status": goal["status"], "target_date": target_date, "base_target": base, "adjusted_target": adjusted,
            "inflation": infl, "allocated": allocated, "remaining": remaining, "months_left": months_left,
            "required_monthly": required, "pct": min(allocated / adjusted * 100, 100) if adjusted else 0.0,
            "recent_rate": recent_monthly_rate, "est_completion": est,
            "on_pace": est is not None and est <= target_date}


def goal_feasibility(metrics: list[dict], surplus: float) -> list[dict]:
    """Walk goals in priority order, committing the monthly surplus to each in turn."""
    left = max(surplus, 0.0)
    out = []
    for g in sorted([m for m in metrics if m["status"] == "active"],
                    key=lambda m: (PRIORITY_ORDER.get(m["priority"], 1), m["target_date"])):
        need = g["required_monthly"]
        if g["remaining"] <= 0:
            state, covered = "complete", 0.0
        elif need <= left + 1e-9:
            state, covered = "affordable", need
        elif left > 0:
            state, covered = "partial", left
        else:
            state, covered = "unfunded", 0.0
        left -= covered
        out.append({**g, "state": state, "covered": covered, "shortfall": max(need - covered, 0.0)})
    return out


def shortfall_options(g: dict, available: float, today: date, avg_wants: float = 0.0) -> list[str]:
    """Concrete, number-backed options for an unaffordable goal."""
    from utils.format import money
    short, opts = g["shortfall"], []
    if available > 0 and g["remaining"] > 0:
        d = add_months(today, math.ceil(g["remaining"] / available))
        opts.append(f"Extend the target date to about {d.strftime('%b %Y')} (at {money(available)} per month).")
    opts.append(f"Reduce the target cost by about {money(short * max(g['months_left'], 1))}.")
    opts.append(f"Increase monthly savings by {money(short)}.")
    if avg_wants > 0:
        opts.append(f"Trim discretionary spending - your recent average on wants is {money(avg_wants)} per month.")
    opts.append("Lower the priority of other goals so this one is funded first.")
    return opts


def emergency_target(essential_monthly: float, months: int) -> float:
    return essential_monthly * months


def essential_monthly_expense(df: pd.DataFrame, n: int = 3, today: date | None = None) -> float:
    s = monthly_summary(df)
    avg, _ = average_monthly(s, n, today)
    return float(avg.get("needs", 0.0))


# ------------------------------------------------------------------ net worth
def latest_valuations(al: pd.DataFrame, as_of=None) -> pd.DataFrame:
    if al.empty:
        return al
    d = al.copy()
    d["valuation_date"] = pd.to_datetime(d["valuation_date"])
    d["current_value"] = pd.to_numeric(d["current_value"]).astype(float)
    if as_of is not None:
        d = d[d["valuation_date"] <= pd.Timestamp(as_of)]
    d = d.sort_values(["valuation_date", "created_at"] if "created_at" in d else ["valuation_date"])
    return d.groupby(["record_type", "name"], as_index=False).tail(1)


def net_worth(al: pd.DataFrame, balances: pd.DataFrame | None = None, include_accounts: bool = True) -> dict:
    cur = latest_valuations(al)
    assets = float(cur.loc[cur["record_type"] == "asset", "current_value"].sum()) if len(cur) else 0.0
    liabs = float(cur.loc[cur["record_type"] == "liability", "current_value"].sum()) if len(cur) else 0.0
    acc_assets = acc_liabs = 0.0
    if include_accounts and balances is not None and len(balances):
        acc_assets = float(balances.loc[balances["balance"] > 0, "balance"].sum())
        acc_liabs = float(-balances.loc[balances["balance"] < 0, "balance"].sum())
    return {"assets": assets + acc_assets, "liabilities": liabs + acc_liabs, "net_worth": assets + acc_assets - liabs - acc_liabs,
            "manual_assets": assets, "manual_liabilities": liabs, "account_assets": acc_assets, "account_liabilities": acc_liabs}


def net_worth_timeline(al: pd.DataFrame) -> pd.DataFrame:
    if al.empty:
        return pd.DataFrame(columns=["date", "assets", "liabilities", "net_worth"])
    dates = sorted(pd.to_datetime(al["valuation_date"]).unique())
    rows = []
    for dt in dates:
        cur = latest_valuations(al, dt)
        a = cur.loc[cur["record_type"] == "asset", "current_value"].sum()
        li = cur.loc[cur["record_type"] == "liability", "current_value"].sum()
        rows.append((pd.Timestamp(dt), float(a), float(li), float(a - li)))
    return pd.DataFrame(rows, columns=["date", "assets", "liabilities", "net_worth"])


# ------------------------------------------------------------------ analytics helpers
def unusual_months(summary: pd.DataFrame, z: float = 1.5) -> pd.DataFrame:
    """Months whose consumption is unusually high vs the other months (needs >= 4 months)."""
    if len(summary) < 4:
        return summary.iloc[0:0]
    x = summary["consumption"]
    sd = x.std(ddof=0)
    if sd == 0:
        return summary.iloc[0:0]
    return summary[(x - x.mean()) / sd > z]


def recurring_expenses(df: pd.DataFrame, min_months: int = 3, tolerance: float = 0.15) -> pd.DataFrame:
    e = df[df["transaction_type"] == "expense"].copy()
    cols = ["description", "months", "avg_amount", "last_date"]
    if e.empty:
        return pd.DataFrame(columns=cols)
    e["key"] = e["description"].str.strip().str.lower()
    e = e[e["key"] != ""]
    e["m"] = e["transaction_date"].dt.to_period("M")
    rows = []
    for key, g in e.groupby("key"):
        per_month = g.groupby("m")["amount"].sum()
        if len(per_month) >= min_months and per_month.mean() > 0 and per_month.std(ddof=0) / per_month.mean() <= tolerance:
            rows.append((g["description"].iloc[-1], len(per_month), float(per_month.mean()), g["transaction_date"].max()))
    return pd.DataFrame(rows, columns=cols).sort_values("avg_amount", ascending=False).reset_index(drop=True)


def generate_insights(df: pd.DataFrame, summary: pd.DataFrame, month, targets: dict, money_fn) -> list[dict]:
    """Rule-based observations. Every insight states the period and figures it is based on."""
    out: list[dict] = []
    ms = month_start(month)
    label = ms.strftime("%B %Y")
    prior = summary[summary.index < ms].tail(3)
    if ms not in summary.index:
        return out
    cur = summary.loc[ms]
    if cur["consumption"] > 0 and cur["income"] == 0:
        out.append({"tone": "warn", "title": f"No income recorded in {label}",
                    "detail": "Savings rate can't be calculated until income is added for this month."})
    elif cur["income"] > 0:
        target = float(targets.get("savings", 20))
        rate = cur["savings_rate"]
        tone = "good" if rate >= target else "warn"
        out.append({"tone": tone, "title": f"Savings rate {rate:.0f}% in {label}",
                    "detail": f"You kept {money_fn(cur['savings'])} of {money_fn(cur['income'])} income; your target is {target:.0f}%."})
        wants_share = cur["wants"] / cur["income"] * 100
        if wants_share > float(targets.get("wants", 30)):
            out.append({"tone": "warn", "title": f"Wants took {wants_share:.0f}% of income in {label}",
                        "detail": f"{money_fn(cur['wants'])} on wants versus a {targets.get('wants', 30):.0f}% target."})
    if len(prior) >= 2:
        s_prior, e_prior = prior.index.min(), month_end(prior.index.max())
        prev = category_spend(df, s_prior, e_prior)
        now = category_spend(df, ms, month_end(ms))
        avg_prev = (prev.set_index("category")["amount"] / len(prior)) if len(prev) else pd.Series(dtype=float)
        changes = []
        for _, r in now.iterrows():
            base = float(avg_prev.get(r["category"], 0.0))
            diff = r["amount"] - base
            if base > 0 and diff >= max(500, 0.2 * base):
                changes.append((diff, r["category"], r["amount"], base))
        for diff, cat, amt, base in sorted(changes, reverse=True)[:3]:
            out.append({"tone": "warn", "title": f"{cat} is up {money_fn(diff)}",
                        "detail": f"You spent {money_fn(amt)} on {cat} in {label}, versus an average of {money_fn(base)} "
                                  f"over the previous {len(prior)} months."})
        for cat, base in avg_prev.items():
            amt = float(now.set_index("category")["amount"].get(cat, 0.0)) if len(now) else 0.0
            if base - amt >= max(1000, 0.3 * base):
                out.append({"tone": "good", "title": f"{cat} is down {money_fn(base - amt)}",
                            "detail": f"{money_fn(amt)} in {label} versus a {len(prior)}-month average of {money_fn(base)}."})
                break
    return out
