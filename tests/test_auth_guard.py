"""Auth logic that must hold without any real Supabase credentials."""
import time

import pytest
from streamlit.testing.v1 import AppTest

from pathlib import Path

from services import auth

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_password_and_email_validation():
    assert auth.validate_password("Abcdefg1") == []
    assert auth.validate_password("short") and auth.validate_password("alllowercase1") and auth.validate_password("NoDigitsHere")
    assert auth.validate_email("a.b+c@mail.example.in") and not auth.validate_email("no-at.example.com") and not auth.validate_email("")


def test_verifier_store_is_single_use_and_expires(monkeypatch):
    auth._stash("n1", "verifier-1")
    assert auth._pop("n1") == "verifier-1" and auth._pop("n1") is None          # single use
    assert auth._pop("unknown") is None
    auth._stash("n2", "v2")
    real = time.time
    monkeypatch.setattr(auth.time, "time", lambda: real() + auth.VERIFIER_TTL + 5)
    assert auth._pop("n2") is None                                              # expired


def test_unauthenticated_user_sees_login_not_dashboard(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("APP_URL", "http://localhost:8501")
    monkeypatch.setenv("GOOGLE_LOGIN_ENABLED", "0")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any("Sign in" in b.label for b in at.button) or at.get("form_submit_button")
    assert not any(b.label == "Transactions" for b in at.sidebar.button)       # no navigation without a session


def test_forged_session_state_is_not_authentication(monkeypatch):
    """Putting a fake user id in session_state must not grant access (token is re-validated with Supabase and fails)."""
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:9")           # unreachable -> validation can't succeed
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("APP_URL", "http://localhost:8501")
    monkeypatch.setenv("GOOGLE_LOGIN_ENABLED", "0")
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["user_id"] = "victim"
    at.session_state["_profile"] = {"id": "victim"}
    at.session_state["_auth"] = auth.AuthSession("forged", "forged", int(time.time()) + 3000, "victim", "v@x.com", "V", validated_at=0)
    at.run()
    assert not any(b.label == "Transactions" for b in at.sidebar.button)
    assert "_auth" not in at.session_state or at.session_state["_auth"] is None


def test_missing_configuration_shows_setup_screen_not_fake_login(monkeypatch):
    for k in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "APP_URL"):
        monkeypatch.delenv(k, raising=False)
    from services import config
    monkeypatch.setattr(config, "get", lambda n, d=None: None)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any("isn't configured" in e.value for e in at.error)
