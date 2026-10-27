"""OPTIONAL end-to-end isolation test against a real Supabase project (skipped unless credentials are set).

Create two throwaway, email-confirmed test users in a NON-production project, apply database/schema.sql, then export:
  SUPABASE_URL, SUPABASE_ANON_KEY,
  FINLIFE_TEST_EMAIL_A / FINLIFE_TEST_PASSWORD_A, FINLIFE_TEST_EMAIL_B / FINLIFE_TEST_PASSWORD_B
"""
import os

import pytest

NEEDED = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "FINLIFE_TEST_EMAIL_A", "FINLIFE_TEST_PASSWORD_A", "FINLIFE_TEST_EMAIL_B", "FINLIFE_TEST_PASSWORD_B"]
pytestmark = pytest.mark.skipif(any(not os.getenv(k) for k in NEEDED), reason="Supabase test credentials not configured")


def _login(suffix):
    from supabase import create_client
    from services.repo import build_repo
    c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
    s = c.auth.sign_in_with_password({"email": os.environ[f"FINLIFE_TEST_EMAIL_{suffix}"], "password": os.environ[f"FINLIFE_TEST_PASSWORD_{suffix}"]}).session
    return build_repo(s.access_token, s.user.id), s.user.id, s.access_token


def test_users_are_isolated_by_row_level_security():
    a, a_id, _ = _login("A")
    b, b_id, b_token = _login("B")
    a.get_profile(); a.seed_defaults()
    acc = a.select("accounts")[0]["id"]
    row = a.insert("transactions", {"account_id": acc, "transaction_type": "income", "amount": 123.45, "transaction_date": "2026-01-01", "description": "rls-test"})[0]
    try:
        assert b.select("transactions") == [] or all(r["user_id"] == b_id for r in b.select("transactions"))
        # B bypasses the Repo filter and talks to the API directly: RLS alone must hide and protect A's row.
        direct = b._c.table("transactions").select("*").eq("id", row["id"]).execute().data
        assert direct == []
        b._c.table("transactions").update({"amount": 1}).eq("id", row["id"]).execute()
        b._c.table("transactions").delete().eq("id", row["id"]).execute()
        assert a.select("transactions")[0]["amount"] == 123.45
        with pytest.raises(Exception):   # forged ownership is rejected by RLS WITH CHECK
            b._c.table("transactions").insert({"user_id": a_id, "account_id": acc, "transaction_type": "income", "amount": 5, "transaction_date": "2026-01-01"}).execute()
        with pytest.raises(Exception):   # composite FK blocks pointing B's rows at A's account
            b._c.table("transactions").insert({"user_id": b_id, "account_id": acc, "transaction_type": "income", "amount": 5, "transaction_date": "2026-01-01"}).execute()
    finally:
        a.delete("transactions", row["id"])
