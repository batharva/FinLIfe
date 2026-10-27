"""FinLife - personal finance & financial life planning. Entry point: `streamlit run app.py`."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from components import ui
from components.ctx import Ctx
from components.theme import theme_css
from services import auth, config, data, finance as fin
from services.repo import DataError, SessionExpired, build_repo
from utils.format import month_label

NAV = [("overview", "Overview", ":material/dashboard:"), ("transactions", "Transactions", ":material/receipt_long:"),
       ("budgets", "Budgets", ":material/pie_chart:"), ("analytics", "Analytics", ":material/monitoring:"),
       ("goals", "Financial Goals", ":material/flag:"), ("investment", "Investment Planner", ":material/trending_up:"),
       ("emergency", "Emergency Fund", ":material/health_and_safety:"), ("networth", "Net Worth", ":material/account_balance:"),
       ("reports", "Reports", ":material/description:"), ("settings", "Settings", ":material/settings:")]
SLUGS = [n[0] for n in NAV]


def navigate(slug: str) -> None:
    st.session_state["page"] = slug
    st.query_params["page"] = slug


def _page() -> str:
    if "page" not in st.session_state:
        q = st.query_params.get("page")
        st.session_state["page"] = q if q in SLUGS else "overview"
    return st.session_state["page"]


def _render_page(slug: str, ctx: Ctx) -> None:
    import importlib
    importlib.import_module(f"views.{slug}").render(ctx)


def _sidebar(profile: dict, sess: auth.AuthSession, ds: data.Dataset, today: date) -> pd.Timestamp:
    with st.sidebar:
        ui.md(ui.brand())
        st.caption(today.strftime("%A, %d %B %Y"))
        first = ds.tx["transaction_date"].min() if len(ds.tx) else pd.Timestamp(today)
        start = min(fin.month_start(first), fin.month_start(today) - pd.DateOffset(months=11))
        months = list(pd.date_range(start, fin.month_start(today), freq="MS"))[::-1]
        month = st.selectbox("Reporting month", months, format_func=month_label, key="month")
        cur = _page()
        for slug, label, icon in NAV:
            if st.button(label, icon=icon, key=f"nav_{slug}", type="primary" if slug == cur else "secondary", use_container_width=True):
                navigate(slug)
                st.rerun()
        st.divider()
        name = profile.get("full_name") or sess.email
        ui.md(f'<div style="font-weight:600;color:var(--text)">{ui.esc(name)}</div><div class="fl-muted" style="font-size:.8rem">{ui.esc(sess.email)}</div>')
        if st.button("Sign out", icon=":material/logout:", key="signout", use_container_width=True):
            auth.sign_out("You've been signed out.")
            st.rerun()
    return month


def main() -> None:
    st.set_page_config(page_title="FinLife", page_icon=":material/account_balance_wallet:", layout="wide",
                       initial_sidebar_state="expanded")
    from views import auth_view

    if (miss := config.missing()):
        st.markdown(theme_css("system", True), unsafe_allow_html=True)
        auth_view.setup_screen(miss)
        return
    err = auth.handle_redirect()
    sess = auth.current_session()
    if sess is None:
        st.markdown(theme_css("system", True), unsafe_allow_html=True)
        auth.flush_cookies()
        auth_view.render(err)
        return
    if sess.recovery:
        st.markdown(theme_css("system", True), unsafe_allow_html=True)
        auth_view.new_password_screen()
        return

    # ---- authenticated ----
    repo = st.session_state.get("_repo")
    if repo is None or st.session_state.get("_repo_token") != sess.access_token:
        repo = build_repo(sess.access_token, sess.user_id)
        st.session_state["_repo"], st.session_state["_repo_token"] = repo, sess.access_token
    try:
        profile = st.session_state.get("_profile")
        if profile is None or profile.get("id") != sess.user_id:
            profile = repo.get_profile(sess.full_name)
            if not profile.get("seeded"):
                repo.seed_defaults()
                profile = repo.get_profile(sess.full_name)
            st.session_state["_profile"] = profile
        ds = data.load(repo)
    except SessionExpired:
        auth.sign_out("Your session expired. Please sign in again.")
        st.rerun()
        return
    except DataError as e:
        st.markdown(theme_css("system"), unsafe_allow_html=True)
        st.error(str(e))
        if st.button("Try again"):
            st.rerun()
        return

    st.markdown(theme_css(profile.get("preferred_theme", "system")), unsafe_allow_html=True)
    auth.flush_cookies()
    today = date.today()
    month = _sidebar(profile, sess, ds, today)
    ui.show_flash()
    ctx = Ctx(repo=repo, ds=ds, profile=profile, session=sess, month=month, today=today, navigate=navigate)
    _render_page(_page(), ctx)


if __name__ == "__main__":
    main()
