from datetime import datetime, timezone
from models.supabase_client import supabase_admin


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _class_label(row: dict) -> str:
    if not row:
        return "—"
    name = (row.get("name") or "").strip()
    grade = (row.get("grade") or "").strip()
    section = (row.get("section") or "").strip()
    if name:
        return f"{name}{f' — {section}' if section else ''}"
    if grade:
        return f"{grade}{f' — {section}' if section else ''}"
    return "—"


def list_classes(school_id: str, query: str = None):
    try:
        q = (
            supabase_admin.table("classes")
            .select("id, school_id, name, grade, section")
            .eq("school_id", school_id)
            .order("grade")
        )
        if query:
            term = query.strip()
            q = q.or_(
                f"name.ilike.%{term}%,"
                f"grade.ilike.%{term}%,"
                f"section.ilike.%{term}%"
            )
        rows = q.execute().data or []
    except Exception:
        return []

    for row in rows:
        row["label"] = _class_label(row)
    return rows


def get_class_by_id(class_id: str, school_id: str):
    try:
        row = (
            supabase_admin.table("classes")
            .select("id, school_id, name, grade, section")
            .eq("id", class_id)
            .eq("school_id", school_id)
            .single()
            .execute()
            .data
        )
        if row:
            row["label"] = _class_label(row)
        return row
    except Exception:
        return None


def get_class_map(school_id: str):
    classes = list_classes(school_id)
    return {c["id"]: c for c in classes}


def get_class_teacher_ids(class_id: str):
    try:
        rows = (
            supabase_admin.table("teacher_classes")
            .select("teacher_id")
            .eq("class_id", class_id)
            .execute()
            .data or []
        )
        return [r["teacher_id"] for r in rows if r.get("teacher_id")]
    except Exception:
        return []


def get_available_teachers(school_id: str):
    try:
        rows = (
            supabase_admin.table("teachers")
            .select("id, full_name, employee_id, designation, status")
            .eq("school_id", school_id)
            .order("full_name")
            .execute()
            .data or []
        )
    except Exception:
        return []
    return rows


def get_class_teachers(class_id: str, school_id: str):
    teacher_ids = get_class_teacher_ids(class_id)
    if not teacher_ids:
        return []
    try:
        rows = (
            supabase_admin.table("teachers")
            .select("id, full_name, employee_id, designation, status")
            .eq("school_id", school_id)
            .in_("id", teacher_ids)
            .order("full_name")
            .execute()
            .data or []
        )
        return rows
    except Exception:
        return []


def _sync_class_teachers(class_id: str, school_id: str, teacher_ids: list):
    wanted = {t for t in (teacher_ids or []) if t}
    existing = set(get_class_teacher_ids(class_id))

    for tid in existing - wanted:
        (
            supabase_admin.table("teacher_classes")
            .delete()
            .eq("class_id", class_id)
            .eq("teacher_id", tid)
            .execute()
        )

    for tid in wanted - existing:
        supabase_admin.table("teacher_classes").insert({
            "school_id": school_id,
            "class_id": class_id,
            "teacher_id": tid,
        }).execute()


def create_class(school_id: str, data: dict, teacher_ids: list = None):
    name = (data.get("name") or "").strip()
    grade = (data.get("grade") or "").strip()
    section = (data.get("section") or "").strip()
    if not name and grade:
        name = f"{grade}{f' {section}' if section else ''}"

    payload = {
        "school_id": school_id,
        "name": name or None,
        "grade": grade or None,
        "section": section or None,
        "updated_at": _now_iso(),
    }
    result = supabase_admin.table("classes").insert(payload).execute()
    row = result.data[0] if result.data else None
    if row and teacher_ids is not None:
        _sync_class_teachers(row["id"], school_id, teacher_ids)
    if row:
        row["label"] = _class_label(row)
    return row


def update_class(class_id: str, school_id: str, data: dict, teacher_ids: list = None):
    existing = get_class_by_id(class_id, school_id)
    if not existing:
        return None

    name = (data.get("name") or "").strip()
    grade = (data.get("grade") or "").strip()
    section = (data.get("section") or "").strip()
    if not name and grade:
        name = f"{grade}{f' {section}' if section else ''}"

    payload = {
        "name": name or None,
        "grade": grade or None,
        "section": section or None,
        "updated_at": _now_iso(),
    }
    result = (
        supabase_admin.table("classes")
        .update(payload)
        .eq("id", class_id)
        .eq("school_id", school_id)
        .execute()
    )
    row = result.data[0] if result.data else None
    if row and teacher_ids is not None:
        _sync_class_teachers(class_id, school_id, teacher_ids)
    if row:
        row["label"] = _class_label(row)
    return row


def delete_class(class_id: str, school_id: str):
    try:
        # Prevent orphaning students.
        students = (
            supabase_admin.table("students")
            .select("id")
            .eq("school_id", school_id)
            .eq("class_id", class_id)
            .limit(1)
            .execute()
            .data or []
        )
        if students:
            return False, "Cannot delete class with enrolled students. Reassign students first."

        supabase_admin.table("teacher_classes").delete().eq("class_id", class_id).execute()
        result = (
            supabase_admin.table("classes")
            .delete()
            .eq("id", class_id)
            .eq("school_id", school_id)
            .execute()
        )
        return bool(result.data), None
    except Exception:
        return False, "Could not delete class."


def get_students_in_class(class_id: str, school_id: str):
    try:
        rows = (
            supabase_admin.table("students")
            .select("id, full_name, admission_number, roll_number, status, class_grade, section, class_id")
            .eq("school_id", school_id)
            .eq("class_id", class_id)
            .order("full_name")
            .execute()
            .data or []
        )
        return rows
    except Exception:
        return []


def get_students_for_assignment(school_id: str):
    try:
        rows = (
            supabase_admin.table("students")
            .select("id, full_name, admission_number, class_id, class_grade, section, status")
            .eq("school_id", school_id)
            .order("full_name")
            .execute()
            .data or []
        )
        return rows
    except Exception:
        return []


def bulk_assign_students_to_class(school_id: str, class_id: str, student_ids: list):
    cls = get_class_by_id(class_id, school_id)
    if not cls:
        return 0

    grade = cls.get("grade") or cls.get("name")
    section = cls.get("section")
    count = 0
    for sid in set(student_ids or []):
        try:
            result = (
                supabase_admin.table("students")
                .update({
                    "class_id": class_id,
                    "class_grade": grade,
                    "section": section,
                    "updated_at": _now_iso(),
                })
                .eq("id", sid)
                .eq("school_id", school_id)
                .execute()
            )
            if result.data:
                count += 1
        except Exception:
            continue
    return count
