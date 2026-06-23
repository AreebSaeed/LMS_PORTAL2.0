from models.supabase_client import supabase_admin
from models.timetable.constants import TIMETABLE_TABLE
from models.timetable.helpers import (
    class_label,
    normalize_class_slots,
    normalize_slot,
    sort_slots,
    time_str,
)


def _slot_payload(teacher_id: str, school_id: str, data: dict) -> dict:
    return {
        "teacher_id": teacher_id,
        "school_id": school_id,
        "class_id": data.get("class_id") or None,
        "subject_id": data.get("subject_id") or None,
        "day_of_week": data["day_of_week"].lower(),
        "start_time": data["start_time"],
        "end_time": data["end_time"],
        "room": (data.get("room") or "").strip() or None,
    }


def fetch_raw_slots(school_id: str, teacher_id: str = None, class_id: str = None) -> list:
    try:
        q = supabase_admin.table(TIMETABLE_TABLE).select("*").eq("school_id", school_id)
        if teacher_id:
            q = q.eq("teacher_id", teacher_id)
        if class_id:
            q = q.eq("class_id", class_id)
        return q.execute().data or []
    except Exception:
        return []


def find_overlapping_slots(
    school_id: str,
    class_id: str,
    day_of_week: str,
    start_time: str,
    end_time: str,
    exclude_slot_id: str = None,
) -> list:
    try:
        q = (
            supabase_admin.table(TIMETABLE_TABLE)
            .select("*")
            .eq("school_id", school_id)
            .eq("class_id", class_id)
            .eq("day_of_week", day_of_week)
            .lt("start_time", end_time)
            .gt("end_time", start_time)
        )
        if exclude_slot_id:
            q = q.neq("id", exclude_slot_id)
        return q.execute().data or []
    except Exception:
        return []


def find_teacher_overlapping_slots(
    school_id: str,
    teacher_id: str,
    day_of_week: str,
    start_time: str,
    end_time: str,
    exclude_slot_id: str = None,
) -> list:
    try:
        q = (
            supabase_admin.table(TIMETABLE_TABLE)
            .select("*")
            .eq("school_id", school_id)
            .eq("teacher_id", teacher_id)
            .eq("day_of_week", day_of_week)
            .lt("start_time", end_time)
            .gt("end_time", start_time)
        )
        if exclude_slot_id:
            q = q.neq("id", exclude_slot_id)
        return q.execute().data or []
    except Exception:
        return []


def delete_slots_by_ids(school_id: str, slot_ids: list) -> None:
    for slot_id in slot_ids:
        (
            supabase_admin.table(TIMETABLE_TABLE)
            .delete()
            .eq("id", slot_id)
            .eq("school_id", school_id)
            .execute()
        )


def insert_slot(teacher_id: str, school_id: str, data: dict):
    try:
        result = (
            supabase_admin.table(TIMETABLE_TABLE)
            .insert(_slot_payload(teacher_id, school_id, data))
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def update_slot_by_id(slot_id: str, school_id: str, payload: dict):
    try:
        result = (
            supabase_admin.table(TIMETABLE_TABLE)
            .update(payload)
            .eq("id", slot_id)
            .eq("school_id", school_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def delete_slot_by_id(slot_id: str, school_id: str) -> bool:
    try:
        result = (
            supabase_admin.table(TIMETABLE_TABLE)
            .delete()
            .eq("id", slot_id)
            .eq("school_id", school_id)
            .execute()
        )
        return bool(result.data)
    except Exception:
        return False


def get_teacher_slot(slot_id: str, teacher_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table(TIMETABLE_TABLE)
            .select("*")
            .eq("id", slot_id)
            .eq("teacher_id", teacher_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def _hydrate_slot_rows(rows: list) -> list:
    if not rows:
        return []

    class_ids = {r["class_id"] for r in rows if r.get("class_id")}
    subject_ids = {r["subject_id"] for r in rows if r.get("subject_id")}
    teacher_ids = {r["teacher_id"] for r in rows if r.get("teacher_id")}

    class_map, subject_map, teacher_map = {}, {}, {}
    if class_ids:
        classes = (
            supabase_admin.table("classes")
            .select("id, name, grade, section")
            .in_("id", list(class_ids))
            .execute()
            .data or []
        )
        class_map = {c["id"]: c for c in classes}
    if subject_ids:
        subjects = (
            supabase_admin.table("subjects")
            .select("id, name")
            .in_("id", list(subject_ids))
            .execute()
            .data or []
        )
        subject_map = {s["id"]: s for s in subjects}
    if teacher_ids:
        teachers = (
            supabase_admin.table("teachers")
            .select("id, full_name")
            .in_("id", list(teacher_ids))
            .execute()
            .data or []
        )
        teacher_map = {t["id"]: t["full_name"] for t in teachers}

    out = []
    for row in rows:
        row["class_info"] = class_map.get(row.get("class_id"))
        row["subject_info"] = subject_map.get(row.get("subject_id"))
        row["subject_name"] = (subject_map.get(row.get("subject_id")) or {}).get("name", "Subject")
        row["teacher_name"] = teacher_map.get(row.get("teacher_id"), "—")
        out.append(normalize_slot(row))
    return sort_slots(out)


def fetch_class_timetable(class_id: str, school_id: str) -> list:
    """Load timetable for a class — students/parents sync from this data."""
    if not class_id:
        return []
    from models.parent_portal_model import get_class_timetable
    from models.class_model import get_class_by_id

    rows = get_class_timetable(class_id, school_id)
    cls = get_class_by_id(class_id, school_id)
    for row in rows:
        if cls:
            row["class_info"] = cls
    return normalize_class_slots(rows)


def fetch_school_timetable(school_id: str, class_id: str = None) -> list:
    """All slots for admin view, optionally filtered by class."""
    try:
        q = (
            supabase_admin.table(TIMETABLE_TABLE)
            .select("*")
            .eq("school_id", school_id)
            .order("day_of_week")
        )
        if class_id:
            q = q.eq("class_id", class_id)
        rows = q.execute().data or []
    except Exception:
        return []
    return _hydrate_slot_rows(rows)


def enrich_conflict_slot(row: dict, school_id: str) -> dict:
    """Attach class label and subject name for conflict messages."""
    out = dict(row)
    if row.get("class_id"):
        from models.class_model import get_class_by_id

        cls = get_class_by_id(row["class_id"], school_id)
        if cls:
            out["class_label"] = class_label(cls)
    if row.get("subject_id"):
        try:
            sub = (
                supabase_admin.table("subjects")
                .select("name")
                .eq("id", row["subject_id"])
                .single()
                .execute()
                .data
            )
            if sub:
                out["subject_name"] = sub.get("name")
        except Exception:
            pass
    out["start_time"] = time_str(row.get("start_time"))
    out["end_time"] = time_str(row.get("end_time"))
    return out
