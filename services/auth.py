"""Supabase Auth integration: email/password, Google OAuth (PKCE), password recovery, session restore.

Security notes
- Passwords are sent to Supabase Auth only; they are never stored, logged or kept in session_state.
- OAuth and recovery use PKCE. The code_verifier is held server-side (single-use, 15-minute TTL), never in the URL.
- Tokens live in this browser session's server-side st.session_state only; they are never rendered or put in URLs.
- "Stay signed in" stores the (rotating, revocable) refresh token in a Lax/Secure cookie. Disable with REMEMBER_SESSION=0.
- Every protected page calls current_session(), which refreshes expiring tokens and re-validates the token with
  Supabase Auth every few minutes. A hand-edited st.session_state value cannot pass validation or satisfy RLS.
"""
from __future__ import annotations

import json
import logging
import re
import secrets
import threading
import time
from dataclasses import dataclass, replace
from urllib.parse import quote

import httpx
import streamlit as st
import streamlit.components.v1 as components

from services import config

log = logging.getLogger("finlife.auth")
KEY, COOKIE = "_auth", "fl_rt"
REFRESH_MARGIN, REVALIDATE_EVERY, VERIFIER_TTL = 90, 300, 900
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    refresh_token: str
    expires_at: int
    user_id: str
    email: str
    full_name: str
    validated_at: float
    recovery: bool = False


# ---------------------------------------------------------------- validation
def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match((email or "").strip())) and len(email) <= 254


def validate_password(pw: str) -> list[str]:
    problems = []
    if len(pw or "") < 8:
        problems.append("at least 8 characters")
    if not re.search(r"[a-z]", pw or ""):
        problems.append("a lowercase letter")
    if not re.search(r"[A-Z]", pw or ""):
        problems.append("an uppercase letter")
    if not re.search(r"\d", pw or ""):
        problems.append("a number")
    return problems


# ---------------------------------------------------------------- supabase clients
class _DictStorage:
    """Minimal auth-storage so we can read the PKCE verifier that supabase-auth generates."""
    def __init__(self):
        self.d: dict[str, str] = {}
    def get_item(self, key): return self.d.get(key)
    def set_item(self, key, value): self.d[key] = value
    def remove_item(self, key): self.d.pop(key, None)


def _client(storage=None):
    from supabase import ClientOptions, create_client
    return create_client(config.get("SUPABASE_URL"), config.get("SUPABASE_ANON_KEY"),
                         options=ClientOptions(auto_refresh_token=False, persist_session=False,
                                               flow_type="pkce", storage=storage or _DictStorage()))


def _auth_headers(token: str | None = None) -> dict:
    return {"apikey": config.get("SUPABASE_ANON_KEY"), "Authorization": f"Bearer {token or config.get('SUPABASE_ANON_KEY')}",
            "Content-Type": "application/json"}


# ---------------------------------------------------------------- server-side PKCE verifier store
@st.cache_resource
def _verifiers() -> dict:
    return {"lock": threading.Lock(), "items": {}}


def _stash(nonce: str, verifier: str) -> None:
    v = _verifiers()
    with v["lock"]:
        now = time.time()
        v["items"] = {k: x for k, x in v["items"].items() if x[1] > now}
        v["items"][nonce] = (verifier, now + VERIFIER_TTL)


def _pop(nonce: str) -> str | None:
    v = _verifiers()
    with v["lock"]:
        item = v["items"].pop(nonce, None)
    return item[0] if item and item[1] > time.time() else None


# ---------------------------------------------------------------- cookies (session persistence)
def queue_cookie(name: str, value: str | None, days: int = 30) -> None:
    if not config.flag("REMEMBER_SESSION", "1"):
        return
    st.session_state.setdefault("_cookie_ops", []).append((name, value, days))


def flush_cookies() -> None:
    """Writes queued cookies from a zero-height same-origin component. Call once per run, near the top."""
    ops = st.session_state.pop("_cookie_ops", [])
    if not ops:
        return
    secure = "; Secure" if config.app_url().startswith("https") else ""
    stmts = []
    for name, value, days in ops:
        age = days * 86400 if value else 0
        cookie = f"{name}={quote(value or '')}; Path=/; Max-Age={age}; SameSite=Lax{secure}"
        stmts.append(f"d.cookie={json.dumps(cookie)};")
    js = "var d=(window.parent&&window.parent.document)||document;" + "".join(stmts)
    components.html(f"<script>{js.replace('</', '<\\/')}</script>", height=0)


# ---------------------------------------------------------------- session helpers
def _from_supabase(s, recovery: bool = False) -> AuthSession:
    meta = (s.user.user_metadata or {}) if s.user else {}
    return AuthSession(access_token=s.access_token, refresh_token=s.refresh_token,
                       expires_at=int(s.expires_at or time.time() + 3000), user_id=s.user.id, email=s.user.email or "",
                       full_name=meta.get("full_name") or meta.get("name") or "", validated_at=time.time(), recovery=recovery)


def _store(s: AuthSession) -> AuthSession:
    st.session_state[KEY] = s
    queue_cookie(COOKIE, s.refresh_token)
    return s


def _friendly_auth_error(e: Exception) -> str:
    msg = str(getattr(e, "message", e)).lower()
    if "invalid login" in msg or "invalid credentials" in msg:
        return "Incorrect email or password."
    if "not confirmed" in msg:
        return "Please verify your email first - check your inbox for the confirmation link."
    if "rate limit" in msg or "too many" in msg or "over_" in msg:
        return "Too many attempts. Please wait a few minutes and try again."
    if "weak" in msg or "password" in msg:
        return "That password was rejected. Use a longer, less common password."
    if isinstance(e, httpx.HTTPError):
        return "Couldn't reach the sign-in service. Check your connection and try again."
    log.warning("auth error: %s", type(e).__name__)
    return "Something went wrong. Please try again."


# ---------------------------------------------------------------- public API: flows
def sign_in_email(email: str, password: str) -> tuple[bool, str]:
    if not validate_email(email) or not password:
        return False, "Enter a valid email address and your password."
    try:
        res = _client().auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
        _store(_from_supabase(res.session))
        st.session_state["_cookie_tried"] = True
        return True, ""
    except Exception as e:  # noqa: BLE001 - mapped to a safe message
        return False, _friendly_auth_error(e)


def sign_up_email(name: str, email: str, password: str) -> tuple[bool, str]:
    try:
        _client().auth.sign_up({"email": email.strip().lower(), "password": password,
                                "options": {"data": {"full_name": name.strip()}, "email_redirect_to": config.app_url() + "/"}})
        # Same message whether or not the address already exists (prevents account enumeration).
        return True, "Check your inbox: if this address is new, we've sent a verification link. Verify, then sign in."
    except Exception as e:  # noqa: BLE001
        return False, _friendly_auth_error(e)


def request_password_reset(email: str) -> tuple[bool, str]:
    if not validate_email(email):
        return False, "Enter a valid email address."
    from supabase_auth.helpers import generate_pkce_challenge, generate_pkce_verifier
    verifier = generate_pkce_verifier()
    challenge = generate_pkce_challenge(verifier)
    nonce = secrets.token_urlsafe(16)
    _stash(nonce, verifier)
    try:
        r = httpx.post(f"{config.get('SUPABASE_URL').rstrip('/')}/auth/v1/recover",
                       params={"redirect_to": f"{config.app_url()}/?flow=recovery&n={nonce}"}, headers=_auth_headers(),
                       json={"email": email.strip().lower(), "code_challenge": challenge,
                             "code_challenge_method": "plain" if challenge == verifier else "s256"}, timeout=15)
        if r.status_code == 429:
            return False, "Too many attempts. Please wait a few minutes and try again."
        if r.status_code >= 400:
            log.warning("recover failed: %s", r.status_code)
            return False, "Couldn't send the reset email. Please try again shortly."
    except httpx.HTTPError:
        return False, "Couldn't reach the sign-in service. Check your connection and try again."
    return True, "If an account exists for that address, a reset link is on its way."


def google_login_url() -> str:
    """Builds the Supabase -> Google authorize URL (no network call). Cached per browser session for 10 min."""
    cached = st.session_state.get("_g")
    if cached and time.time() - cached[1] < 600:
        return cached[0]
    storage = _DictStorage()
    nonce = secrets.token_urlsafe(16)
    res = _client(storage).auth.sign_in_with_oauth({"provider": "google", "options": {
        "redirect_to": f"{config.app_url()}/?flow=oauth&n={nonce}", "query_params": {"prompt": "select_account"}}})
    verifier = next((v for k, v in storage.d.items() if k.endswith("code-verifier")), None)
    if verifier:
        _stash(nonce, verifier)
    st.session_state["_g"] = (res.url, time.time())
    return res.url


def update_password(new_password: str) -> tuple[bool, str]:
    s = st.session_state.get(KEY)
    if not s or not s.recovery:
        return False, "This reset link is no longer valid. Request a new one."
    problems = validate_password(new_password)
    if problems:
        return False, "Password needs " + ", ".join(problems) + "."
    try:
        c = _client()
        c.auth.set_session(s.access_token, s.refresh_token)
        c.auth.update_user({"password": new_password})
        st.session_state[KEY] = replace(s, recovery=False)
        return True, "Password updated."
    except Exception as e:  # noqa: BLE001
        return False, _friendly_auth_error(e)


def handle_redirect() -> str | None:
    """Completes OAuth / password-recovery redirects (?code=...&flow=...). Returns an error message, if any."""
    qp = st.query_params
    flow, code, nonce = qp.get("flow"), qp.get("code"), qp.get("n")
    err = qp.get("error_description") or qp.get("error")
    if not (flow or code or err):
        return None
    st.query_params.clear()
    if err:
        return "Sign-in was cancelled or failed: " + str(err)[:200]
    if flow not in ("oauth", "recovery") or not code:
        return None
    verifier = _pop(nonce or "")
    if not verifier:
        return "That sign-in link expired or was already used. Please start again."
    try:
        res = _client().auth.exchange_code_for_session({"auth_code": code, "code_verifier": verifier})
        _store(_from_supabase(res.session, recovery=(flow == "recovery")))
    except Exception as e:  # noqa: BLE001
        return _friendly_auth_error(e)
    st.session_state["_cookie_tried"] = True
    st.rerun()


def current_session() -> AuthSession | None:
    """The ONLY way pages learn who the user is. Returns a server-validated session or None."""
    s = st.session_state.get(KEY)
    if s is None:
        s = _restore_from_cookie()
    if s is None:
        return None
    now = time.time()
    try:
        if s.expires_at - now < REFRESH_MARGIN:
            res = _client().auth.refresh_session(s.refresh_token)
            s = _store(_from_supabase(res.session, s.recovery))
        elif now - s.validated_at > REVALIDATE_EVERY:
            r = _client().auth.get_user(s.access_token)
            if r is None or r.user is None or r.user.id != s.user_id:
                raise ValueError("token rejected")
            s = replace(s, validated_at=now)
            st.session_state[KEY] = s
    except Exception:  # noqa: BLE001 - any failure means the session is no longer trustworthy
        sign_out("Your session expired. Please sign in again.")
        return None
    return s


def _restore_from_cookie() -> AuthSession | None:
    if st.session_state.get("_cookie_tried") or not config.flag("REMEMBER_SESSION", "1"):
        return None
    st.session_state["_cookie_tried"] = True
    try:
        rt = st.context.cookies.get(COOKIE)
    except Exception:  # noqa: BLE001
        rt = None
    if not rt:
        return None
    try:
        res = _client().auth.refresh_session(rt)
        return _store(_from_supabase(res.session))
    except Exception:  # noqa: BLE001
        queue_cookie(COOKIE, None)
        return None


def sign_out(message: str | None = None) -> None:
    """Revokes this session on the server (local scope only), clears local state and the cookie."""
    s = st.session_state.get(KEY)
    if s:
        try:
            httpx.post(f"{config.get('SUPABASE_URL').rstrip('/')}/auth/v1/logout", params={"scope": "local"},
                       headers=_auth_headers(s.access_token), timeout=10)
        except httpx.HTTPError:
            pass
    keep = {k: st.session_state[k] for k in ("_cookie_ops",) if k in st.session_state}
    st.session_state.clear()
    st.session_state.update(keep)
    st.session_state["_cookie_tried"] = True          # don't resurrect from the stale cookie snapshot
    queue_cookie(COOKIE, None)
    if message:
        st.session_state["_notice"] = message
