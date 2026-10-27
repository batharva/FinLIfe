# FinLife

*Understand your money. Design your future.*

A multi-user personal finance and financial-goal planning app built with **Streamlit**, **Supabase** (PostgreSQL + Auth), **pandas** and **Plotly**. Users register, verify their email (or use Google), record income and spending, set budgets and goals, explore educational investment scenarios, and track emergency fund and net worth. All data is stored per user in PostgreSQL with Row Level Security.

---

## Honest status

| Area | State |
|---|---|
| Financial logic, CSV, repository ownership rules, recurring posting, auth guards, UI rendering of all 10 pages, form writes | **Implemented and covered by 60 automated tests (all passing)** |
| Visual check in Chromium (light, dark, explicit-dark on a light OS) | **Done on Overview, Transactions, Analytics, Goals, Investment Planner** with a stubbed login. Budgets, Net Worth, Reports, Settings render in tests but I did not eyeball them |
| Supabase email/password, Google OAuth, password reset, session restore | **Implemented against the documented Supabase Auth APIs but NOT exercised against a live project** (no credentials were available). You must run the checklist in "Acceptance checklist" below |
| Row Level Security + cross-user isolation in PostgreSQL | **SQL written; not applied to a live database by me.** `tests/test_rls_integration.py` verifies it against a real project when you provide two test users |
| Deployment to Streamlit Community Cloud | **Not deployed** |

Nothing here claims more than the table says.

## Features

Overview dashboard (real data only, onboarding state when empty), transactions (add / edit / delete / duplicate / search / filter / sort, recurring templates, CSV import with duplicate protection, CSV export), budgets with 75/90/100% alerts and needs-wants-savings targets, analytics (1 to 12 months and custom ranges, a detailed review after 3 months of data, rule-based observations that cite their figures), goals with inflation-adjusted targets, monthly requirement, feasibility against your actual surplus and number-backed options when a goal is unaffordable, explicit allocation of savings to goals, an educational investment planner (lower/middle/higher scenarios, fees, horizon-aware guidance, no guarantees, no trades), emergency fund planner, net worth with manual valuations and history, reports (CSV and printable HTML), settings (profile, currency, Light/Dark/System theme saved to your profile, accounts, categories, data erase).

**Accounting rules** (see `services/finance.py`): transfers and credit-card bill payments are neutral; investments are allocations, not consumption; card purchases count when made; refunds reduce spending in their category; cash flow, consumption, balances and net worth are kept distinct. "Insights" are simple rules on your own numbers, not machine learning.

## Project layout

```
app.py                  entry point, auth gate, sidebar navigation
views/                  one module per page (named views/, not pages/, so Streamlit's
                        auto-routing can never expose a page before the auth gate runs)
components/             theme (CSS tokens + Plotly layout), ui helpers, charts, context
services/               auth.py, repo.py (DB layer), data.py (cached loading), finance.py (pure maths),
                        csvio.py, recurring.py, config.py
database/schema.sql     tables, constraints, indexes, triggers, RLS policies
tests/                  pytest suite (+ in-memory fakes and a UI harness)
.streamlit/             config.toml (theme), secrets.toml.example
```

## 1. Supabase setup

1. Create a project at supabase.com. Note **Project URL** and the **publishable / anon key** (Settings > API). **Never use or commit the `service_role` key**; FinLife does not need it.
2. SQL Editor: paste and run `database/schema.sql` (re-runnable). It creates all tables, composite `(id, user_id)` foreign keys (a row can never reference another user's account/category), RLS policies (`user_id = auth.uid()` for every operation, with `WITH CHECK`), a trigger that creates each profile on sign-up, and revokes table access from the `anon` role.
3. Authentication > Providers > **Email**: enable; keep **Confirm email** on (this is what sends the verification email).
4. Authentication > URL Configuration:
   - **Site URL**: your app URL, e.g. `https://YOUR-APP.streamlit.app`
   - **Redirect URLs**: add `https://YOUR-APP.streamlit.app/**` and, for local work, `http://localhost:8501/**`. The `/**` wildcard is required because FinLife appends `?flow=...&n=...` to the redirect.
5. (Recommended) Authentication > Emails: brand the templates. Password-reset and OAuth use PKCE, so no token ever appears in a URL.

## 2. Google sign-in

1. Google Cloud Console > APIs & Services > **OAuth consent screen**: configure (External), add your app name and support email.
2. **Credentials > Create credentials > OAuth client ID > Web application**.
   - **Authorized JavaScript origins**: your app origin (`https://YOUR-APP.streamlit.app`, and `http://localhost:8501` for local).
   - **Authorized redirect URIs**: the Supabase callback, exactly `https://YOUR-PROJECT-REF.supabase.co/auth/v1/callback`. (Google redirects to *Supabase*, which then redirects to your app. Do not put the Streamlit URL here.)
3. Copy the client ID and secret into Supabase > Authentication > Providers > **Google** and enable it. The secret lives only in Supabase, never in this code base.
4. Set `GOOGLE_LOGIN_ENABLED = "0"` in secrets to hide the button until Google is configured.

Notes: the "Continue with Google" button opens in a new tab (Streamlit's link button); you finish signing in there. Google users and email users are separate Supabase identities unless you enable account linking in Supabase.

## 3. Run locally

```bash
python -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # or: cp .env.example .env
# fill in SUPABASE_URL, SUPABASE_ANON_KEY, APP_URL=http://localhost:8501
streamlit run app.py
```
Without those values the app shows a setup screen; it never fakes a login.

## 4. Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repository (`.gitignore` already excludes `.env` and `secrets.toml`).
2. share.streamlit.io > **Create app** > pick the repo, branch and `app.py`.
3. App > Settings > **Secrets**: paste the contents of `.streamlit/secrets.toml.example` with real values. Set `APP_URL` to the final public URL.
4. Add that exact URL to Supabase **Site URL** / **Redirect URLs** (step 1.4) and to Google's JavaScript origins (step 2.2).
5. Local vs production: local uses `http://localhost:8501`; production uses your `https://...streamlit.app` URL. Only the Google redirect URI (the Supabase callback) is the same in both.

## 5. Tests

```bash
pip install -r requirements.txt
python -m pytest -q
```
No credentials needed for the 60 unit/UI tests. For the optional database-level isolation test, create two throwaway confirmed users in a non-production project and export `FINLIFE_TEST_EMAIL_A/PASSWORD_A/EMAIL_B/PASSWORD_B` (plus `SUPABASE_URL`, `SUPABASE_ANON_KEY`) before running `pytest tests/test_rls_integration.py`.

To look at the UI without Supabase: `FINLIFE_THEME=dark streamlit run tests/_harness.py` (stub login, in-memory demo data, test use only).

## 6. Acceptance checklist (run this on your deployment)

1. Register with email + password; receive the verification email; verify; sign in.
2. Sign out, then "Continue with Google" with a different account.
3. Record income and several expenses; refresh the browser (you stay signed in), sign out and in again, and confirm the data persists. Reboot the app in Streamlit Cloud and confirm it still does.
4. Set budgets; confirm the dashboard and budget bars move.
5. After 3 months of data (or an imported CSV) open Analytics.
6. Create a car goal; compare the required monthly amount with your surplus; try the Investment Planner, Emergency Fund and Net Worth pages.
7. Export CSV; switch to Dark in Settings and navigate/refresh.
8. Sign in as user B and confirm user A's data is invisible; run the RLS integration test.
9. Sign out; open a deep link such as `?page=transactions` and confirm you get the sign-in screen.
10. Forgot password: request a link, open it, set a new password.

## Security model

- Passwords go to Supabase Auth only; never stored, logged or kept in `st.session_state`.
- Every protected run calls `auth.current_session()`: refreshes tokens before expiry, re-validates with Supabase every 5 minutes, signs out on failure. Setting `st.session_state` by hand cannot authenticate (tested).
- Each session's database client carries that user's JWT, so Row Level Security applies; `Repo` additionally forces `user_id` on inserts and scopes updates/deletes, and composite foreign keys block cross-user references.
- OAuth and password reset use PKCE; the verifier is held server-side, single-use, 15-minute TTL (single-process assumption, true on Community Cloud). Tokens are never put in query parameters.
- "Stay signed in" stores Supabase's rotating, revocable refresh token in a `SameSite=Lax` (and `Secure` on HTTPS) cookie. Streamlit cannot set HttpOnly cookies, so an XSS bug would expose it; set `REMEMBER_SESSION = "0"` to disable. All user text is HTML-escaped before rendering; CSV exports neutralise spreadsheet formulas.
- Cached data is keyed by `(user_id, data_version)`; per-user clients are never stored in shared resources.

## Known limits and caveats

- **Theme CSS is tied to Streamlit's DOM.** Native widgets follow your OS via `[theme.light]/[theme.dark]` in `config.toml`; explicit Light/Dark and the app's components use CSS keyed on `data-testid` attributes (Streamlit 1.66 replaced BaseWeb, which broke the first version of this CSS). Re-check dark mode after upgrading Streamlit; `requirements.txt` caps it below 2.0.
- Email verification links land on the app's home page; you then sign in (the link does not auto-sign-in).
- Goal feasibility uses average monthly *savings* (income minus spending) over the last three complete months as the "surplus".
- Deleting the sign-in account itself needs the Supabase dashboard (or a service-role operation); in-app "Erase everything" removes all financial data.
- Terms/privacy text in the register screen is a placeholder summary. Replace it with real legal text before public launch.
- Indian-specific rules (tax, deposit insurance, product limits) are deliberately not hard-coded; the planner links to RBI, SEBI, AMFI and the Income Tax Department instead.
- Not financial advice; no live prices or bank connections; no trades.
