import os
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_config_error: Optional[str] = None
_supabase: Optional[Client] = None
_supabase_admin: Optional[Client] = None


def _read_config():
    global _config_error
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not url or not key or not service_key:
        _config_error = (
            "Missing Supabase environment variables. Set SUPABASE_URL, "
            "SUPABASE_KEY, and SUPABASE_SERVICE_KEY in Vercel project settings."
        )
        return None, None, None

    if url.startswith("postgresql://"):
        _config_error = (
            "SUPABASE_URL must be the Project URL (https://xxx.supabase.co), "
            "not the postgres connection string."
        )
        return None, None, None

    _config_error = None
    return url, key, service_key


def config_error() -> Optional[str]:
    _read_config()
    return _config_error


def _get_supabase() -> Client:
    global _supabase
    if _supabase is not None:
        return _supabase

    url, key, _ = _read_config()
    if not url:
        raise RuntimeError(_config_error or "Supabase is not configured.")

    _supabase = create_client(url, key)
    return _supabase


def _get_supabase_admin() -> Client:
    global _supabase_admin
    if _supabase_admin is not None:
        return _supabase_admin

    url, _, service_key = _read_config()
    if not url:
        raise RuntimeError(_config_error or "Supabase is not configured.")

    _supabase_admin = create_client(url, service_key)
    return _supabase_admin


class _LazySupabase:
    """Defer client creation until first use (required for Vercel cold starts)."""

    def __init__(self, admin: bool = False):
        self._admin = admin

    def _client(self) -> Client:
        return _get_supabase_admin() if self._admin else _get_supabase()

    def __getattr__(self, name):
        return getattr(self._client(), name)


supabase = _LazySupabase(admin=False)
supabase_admin = _LazySupabase(admin=True)
