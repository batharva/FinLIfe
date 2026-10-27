"""Every page renders (empty and populated), and the main write paths work end to end against the in-memory repo."""
import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests import fakes

HARNESS = str(Path(__file__).resolve().parent / "_harness.py")
PAGES = ["overview", "transactions", "budgets", "analytics", "goals", "investment", "emergency", "networth", "reports", "settings"]


def fresh(demo: bool):
    os.environ["FINLIFE_DEMO"] = "1" if demo else "0"
    os.environ["FINLIFE_RESET"] = "1"
    return AppTest.from_file(HARNESS, default_timeout=60)


def go(at, page):
    at.session_state["page"] = page
    at.run()
    return at


@pytest.mark.parametrize("demo", [False, True], ids=["empty", "populated"])
@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page, demo):
    at = fresh(demo)
    at.run()                                   # first run seeds the shared repo
    os.environ["FINLIFE_RESET"] = "0"
    go(at, page)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error or all("isn't configured" not in e.value for e in at.error)


def test_add_expense_end_to_end():
    at = fresh(False)
    at.run()
    go(at, "transactions")
    assert not at.exception
    amt = next(n for n in at.number_input if n.label == "Amount")
    amt.set_value(450.0)
    desc = next(t for t in at.text_input if t.label == "Description")
    desc.set_value("Lunch")
    cat = next(s for s in at.selectbox if s.label == "Category")
    cat.select(next(o for o in cat.options if o == "Essential meals") if "Essential meals" in cat.options else cat.options[1])
    next(b for b in at.button if b.label == "Save transaction").click()
    at.run()
    assert not at.exception
    rows = fakes.SHARED.select("transactions")
    assert len(rows) == 1 and rows[0]["amount"] == 450.0 and rows[0]["description"] == "Lunch" and rows[0]["user_id"] == "user-a"
    go(at, "overview")
    assert not at.exception and any("450" in m.value for m in at.markdown)


def test_validation_blocks_zero_amount():
    at = fresh(False)
    at.run()
    go(at, "transactions")
    next(b for b in at.button if b.label == "Save transaction").click()
    at.run()
    assert any("greater than zero" in e.value for e in at.error)
    assert fakes.SHARED.select("transactions") == []


def test_description_text_is_html_escaped():
    at = fresh(False)
    at.run()
    fakes.SHARED.insert("transactions", {"account_id": fakes.acct_id(fakes.SHARED), "transaction_type": "expense", "amount": 10,
                                         "transaction_date": "2026-10-01", "description": "<img src=x onerror=alert(1)>", "payment_method": "UPI"})
    go(at, "transactions")
    at.session_state["page"] = "transactions"
    at.run()
    html = " ".join(m.value for m in at.markdown)
    assert "<img src=x" not in html


def test_goal_creation_computes_required_monthly():
    at = fresh(True)
    at.run()
    go(at, "goals")
    next(t for t in at.text_input if t.label == "Goal name").set_value("Buy a car")
    next(n for n in at.number_input if n.label.startswith("Target amount")).set_value(600000.0)
    next(b for b in at.button if b.label == "Create goal").click()
    at.run()
    assert not at.exception
    g = fakes.SHARED.select("financial_goals")
    assert len(g) == 1 and g[0]["goal_name"] == "Buy a car"
    text = " ".join(m.value for m in at.markdown)
    assert "needed per month" in text and "Buy a car" in text
