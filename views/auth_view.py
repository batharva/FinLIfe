"""Sign in / register / forgot password / set new password."""
from __future__ import annotations

import streamlit as st

from components import ui
from services import auth, config

TERMS = """**Terms and privacy summary** (replace with your own legal text before launch)

- FinLife is a personal finance tracking and education tool. It does not provide investment, tax or legal advice.
- You enter your own data. FinLife never asks for bank credentials, never moves money and never places trades.
- Your records are stored in a private database where Row Level Security limits every row to your account.
- You can export or delete your data at any time from Settings.
"""


def _hero(subtitle: str) -> None:
    ui.md(f'{ui.brand()}<div style="font-size:1.55rem;font-weight:700;margin:.8rem 0 .2rem;letter-spacing:-.02em;color:var(--text)">'
          f'Understand your money. Design your future.</div><div class="fl-muted" style="margin-bottom:1rem">{ui.esc(subtitle)}</div>')


def _switch(mode: str) -> None:
    st.session_state["_auth_mode"] = mode


def setup_screen(missing: list[str]) -> None:
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        _hero("One more step before FinLife can run.")
        st.error("Supabase isn't configured yet, so sign-in is disabled.")
        st.markdown("Add these values to **.streamlit/secrets.toml** (or environment variables / `.env`):")
        st.code("\n".join(f'{m} = "..."' for m in missing), language="toml")
        st.caption("See README.md > Deployment for where to find each value. FinLife never fakes a login when configuration is missing.")


def render(error: str | None = None) -> None:
    mode = st.session_state.setdefault("_auth_mode", "signin")
    _, mid, _ = st.columns([1, 1.25, 1])
    with mid:
        _hero({"signin": "Sign in to continue.", "register": "Create your free account.",
               "forgot": "We'll email you a reset link."}.get(mode, ""))
        if (n := st.session_state.pop("_notice", None)):
            st.info(n)
        if error:
            st.error(error)
        if mode == "register":
            _register()
        elif mode == "forgot":
            _forgot()
        else:
            _signin()
        ui.md('<div class="fl-muted" style="font-size:.8rem;margin-top:1rem">Your data is private to your account and protected by '
              'database-level access rules. FinLife never asks for bank passwords and never moves money.</div>')


def _signin() -> None:
    with st.form("signin", border=True):
        email = st.text_input("Email", autocomplete="email")
        pw = st.text_input("Password", type="password", autocomplete="current-password")
        go = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if go:
        with st.spinner("Signing in..."):
            ok, msg = auth.sign_in_email(email, pw)
        if ok:
            st.rerun()
        st.error(msg)
    if config.flag("GOOGLE_LOGIN_ENABLED", "1"):
        try:
            st.link_button("Continue with Google", auth.google_login_url(), use_container_width=True, icon=":material/login:")
            st.caption("Opens Google sign-in in a new tab.")
        except Exception:  # noqa: BLE001
            st.warning("Google sign-in couldn't be prepared. Check SUPABASE_URL / SUPABASE_ANON_KEY and the Google provider settings.")
    c1, c2 = st.columns(2)
    c1.button("Create an account", type="tertiary", on_click=_switch, args=("register",), key="to_reg")
    c2.button("Forgot password?", type="tertiary", on_click=_switch, args=("forgot",), key="to_forgot")


def _register() -> None:
    with st.form("register", border=True):
        name = st.text_input("Full name", autocomplete="name")
        email = st.text_input("Email", autocomplete="email")
        pw = st.text_input("Password", type="password", help="At least 8 characters with upper and lower case letters and a number.",
                           autocomplete="new-password")
        pw2 = st.text_input("Confirm password", type="password", autocomplete="new-password")
        agree = st.checkbox("I accept the terms and privacy policy")
        go = st.form_submit_button("Create account", type="primary", use_container_width=True)
    with st.expander("Read the terms and privacy summary"):
        st.markdown(TERMS)
    if go:
        problems = auth.validate_password(pw)
        if not name.strip() or not email.strip() or not pw:
            st.error("Please fill in every field.")
        elif not auth.validate_email(email):
            st.error("That email address doesn't look right.")
        elif problems:
            st.error("Password needs " + ", ".join(problems) + ".")
        elif pw != pw2:
            st.error("The two passwords don't match.")
        elif not agree:
            st.error("Please accept the terms and privacy policy to continue.")
        else:
            with st.spinner("Creating your account..."):
                ok, msg = auth.sign_up_email(name, email, pw)
            (st.success if ok else st.error)(msg)
    st.button("Already registered? Sign in", type="tertiary", on_click=_switch, args=("signin",), key="to_signin1")


def _forgot() -> None:
    with st.form("forgot", border=True):
        email = st.text_input("Email", autocomplete="email")
        go = st.form_submit_button("Send reset link", type="primary", use_container_width=True)
    if go:
        with st.spinner("Sending..."):
            ok, msg = auth.request_password_reset(email)
        (st.success if ok else st.error)(msg)
    st.button("Back to sign in", type="tertiary", on_click=_switch, args=("signin",), key="to_signin2")


def new_password_screen() -> None:
    _, mid, _ = st.columns([1, 1.25, 1])
    with mid:
        _hero("Choose a new password.")
        with st.form("newpw", border=True):
            pw = st.text_input("New password", type="password", autocomplete="new-password")
            pw2 = st.text_input("Confirm new password", type="password", autocomplete="new-password")
            go = st.form_submit_button("Update password", type="primary", use_container_width=True)
        if go:
            if pw != pw2:
                st.error("The two passwords don't match.")
            else:
                ok, msg = auth.update_password(pw)
                if ok:
                    ui.flash("Password updated. You're signed in.")
                    st.rerun()
                st.error(msg)
        st.button("Cancel and sign out", type="tertiary", on_click=lambda: auth.sign_out(), key="cancel_reset")
