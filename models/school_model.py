from models.supabase_client import supabase_admin


def get_all_schools():
    """Fetch all schools. Called by super admin only."""
    result = supabase_admin.table("schools").select("*").order("created_at", desc=True).execute()
    return result.data or []


def get_school_by_id(school_id: str):
    """Fetch a single school by its UUID."""
    result = supabase_admin.table("schools").select("*").eq("id", school_id).single().execute()
    return result.data


def get_school_stats(school_id: str):
    """Return counts of users grouped by role for a given school."""
    profiles = (
        supabase_admin.table("user_profiles")
        .select("role")
        .eq("school_id", school_id)
        .execute()
        .data or []
    )
    stats = {
        "total_users": len(profiles),
        "teachers_count": sum(1 for p in profiles if p["role"] == "teacher"),
        "students_count": sum(1 for p in profiles if p["role"] == "student"),
        "parents_count": sum(1 for p in profiles if p["role"] == "parent"),
        "accountants_count": sum(1 for p in profiles if p["role"] == "accountant"),
    }
    return stats
