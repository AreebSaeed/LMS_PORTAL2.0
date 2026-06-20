import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
service_key: str = os.environ.get("SUPABASE_SERVICE_KEY")

if not url or not key or not service_key:
    raise RuntimeError(
        "Missing Supabase env vars. Copy .env.example to .env and set "
        "SUPABASE_URL, SUPABASE_KEY, and SUPABASE_SERVICE_KEY."
    )
if url.startswith("postgresql://"):
    raise RuntimeError(
        "SUPABASE_URL must be the Project URL (https://xxx.supabase.co), "
        "not the postgres database connection string. "
        "Find it in Supabase → Settings → API → Project URL."
    )

# Public client — respects RLS
supabase: Client = create_client(url, key)

# Admin client — bypasses RLS (use only for super admin operations)
supabase_admin: Client = create_client(url, service_key)
