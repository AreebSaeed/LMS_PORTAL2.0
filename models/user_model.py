from models.supabase_client import supabase, supabase_admin


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
