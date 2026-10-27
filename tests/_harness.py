"""Runs the REAL app with a stubbed login and an in-memory repo - for UI smoke tests and screenshots only.
Never used in production: it is not imported by app.py and lives under tests/."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

import app  # noqa: E402
from services import auth  # noqa: E402
from tests import fakes  # noqa: E402

if not hasattr(fakes, "SHARED") or os.getenv("FINLIFE_RESET") == "1":
    fakes.SHARED = fakes.seeded_repo()
    if os.getenv("FINLIFE_DEMO", "1") == "1":
        fakes.demo_history(fakes.SHARED, months=4)
    fakes.SHARED.update_profile({"preferred_theme": os.getenv("FINLIFE_THEME", "light")})
    os.environ["FINLIFE_RESET"] = "0"
st.cache_data.clear()

SESSION = auth.AuthSession("tok", "rt", int(time.time()) + 36000, "user-a", "demo@finlife.test", "Demo User", time.time())
auth.handle_redirect = lambda: None
auth.current_session = lambda: SESSION
app.config.missing = lambda: []
app.build_repo = lambda token, uid: fakes.SHARED
app.main()
