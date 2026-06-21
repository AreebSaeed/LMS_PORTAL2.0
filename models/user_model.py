import re
from models.supabase_client import supabase, supabase_admin

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def get_profile_by_id(user_id: str):
    """Fetch user profile row by auth user UUID."""
    result = (
        supabase_admin.table("user_profiles")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
    )
    return result.data


def get_users_by_school(school_id: str):
    """Fetch all user profiles belonging to a school."""
    result = (
        supabase_admin.table("user_profiles")
        .select("*")
        .eq("school_id", school_id)
        .execute()
    )
    return result.data or []


def get_auth_email(user_id: str):
    """Fetch the Supabase Auth email for a user UUID."""
    try:
        result = supabase_admin.auth.admin.get_user_by_id(user_id)
        return result.user.email
    except Exception:
        return None


def resolve_login_email(identifier: str):
    """
    Resolve Username / Email / ID to an email for Supabase Auth sign-in.
    Supports email, user UUID, or phone number on the profile.
    """
    identifier = identifier.strip()
    if not identifier:
        return None

    if "@" in identifier:
        return identifier

    if UUID_PATTERN.match(identifier):
        profile = get_profile_by_id(identifier)
        if profile:
            return get_auth_email(profile["id"])
        return None

    result = (
        supabase_admin.table("user_profiles")
        .select("id")
        .eq("phone", identifier)
        .limit(1)
        .execute()
    )
    if result.data:
        return get_auth_email(result.data[0]["id"])

    return None
