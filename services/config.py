"""Configuration from Streamlit secrets (hosting) or environment variables / .env (local)."""
from __future__ import annotations

import os

import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

REQUIRED = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "APP_URL")


def get(name: str, default: str | None = None) -> str | None:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # no secrets file present
        pass
    return os.getenv(name, default)


def missing() -> list[str]:
    return [n for n in REQUIRED if not get(n)]


def app_url() -> str:
    return (get("APP_URL", "http://localhost:8501") or "").rstrip("/")


def flag(name: str, default: str = "1") -> bool:
    return str(get(name, default)).strip().lower() in ("1", "true", "yes", "on")
