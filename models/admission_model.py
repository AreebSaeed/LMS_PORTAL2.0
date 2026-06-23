from models.supabase_client import supabase_admin

ADMISSION_STATUSES = ("pending", "approved", "rejected")


def list_admissions(school_id: str, limit=100):
    try:
        return (
            supabase_admin.table("admissions")
            .select("*")
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []


def create_admission(school_id: str, student_name: str, grade: str = ""):
    payload = {
        "school_id": school_id,
        "student_name": student_name.strip(),
        "grade": (grade or "").strip() or None,
        "status": "pending",
    }
    try:
        result = supabase_admin.table("admissions").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def update_admission_status(school_id: str, admission_id: str, status: str) -> bool:
    if status not in ADMISSION_STATUSES:
        return False
    try:
        (
            supabase_admin.table("admissions")
            .update({"status": status})
            .eq("id", admission_id)
            .eq("school_id", school_id)
            .execute()
        )
        return True
    except Exception:
        return False
