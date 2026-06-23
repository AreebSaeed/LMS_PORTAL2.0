from models.supabase_client import supabase_admin
from models.timetable.helpers import class_label


def teachers_for_select(school_id: str) -> list:
    try:
        rows = (
            supabase_admin.table("teachers")
            .select("id, full_name")
            .eq("school_id", school_id)
            .eq("status", "active")
            .order("full_name")
            .execute()
            .data or []
        )
        return [{"id": t["id"], "name": t["full_name"]} for t in rows]
    except Exception:
        return []


def classes_for_select(school_id: str) -> list:
    from models.class_model import list_classes

    return [{"id": c["id"], "label": class_label(c)} for c in list_classes(school_id)]


def subjects_for_select(school_id: str) -> list:
    try:
        rows = (
            supabase_admin.table("subjects")
            .select("id, name")
            .eq("school_id", school_id)
            .order("name")
            .execute()
            .data or []
        )
        return [{"id": s["id"], "name": s["name"]} for s in rows]
    except Exception:
        return []
