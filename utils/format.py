"""Currency and number formatting (Indian digit grouping for INR)."""
from __future__ import annotations

import math
import re

SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def money(value, currency: str = "INR", decimals: int = 0, signed: bool = False) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    value = float(value)
    neg = value < 0
    s = f"{abs(round(value, decimals)):.{decimals}f}"
    whole, _, frac = s.partition(".")
    if currency == "INR" and len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        whole = f"{head},{tail}"
    elif currency != "INR":
        whole = f"{int(whole):,}"
    out = SYMBOLS.get(currency, "") + whole + (f".{frac}" if frac else "")
    if neg and float(s) != 0:
        return "−" + out
    return ("+" + out) if signed and float(s) != 0 else out


def pct(value, decimals: int = 0) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value:.{decimals}f}%"


def month_label(ts) -> str:
    return ts.strftime("%b %Y")
