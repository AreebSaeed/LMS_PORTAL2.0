"""Shared announcement audience helpers and queries."""

from models.supabase_client import supabase_admin

AUDIENCE_ROLES = ("teachers", "students", "parents")

_ROLE_COLUMN = {
    "teacher": "audience_teachers",
    "student": "audience_students",
    "parent": "audience_parents",
}


def parse_audience_from_form(form):
    """Return (teachers, students, parents) or None if nothing selected."""
    if form.get("audience_all") == "on":
        return True, True, True
    teachers = form.get("audience_teachers") == "on"
    students = form.get("audience_students") == "on"
    parents = form.get("audience_parents") == "on"
    if not (teachers or students or parents):
        return None
    return teachers, students, parents


def audience_summary(teachers: bool, students: bool, parents: bool) -> str:
    if teachers and students and parents:
        return "teachers, students, and parents"
    labels = []
    if teachers:
        labels.append("teachers")
    if students:
        labels.append("students")
    if parents:
        labels.append("parents")
    return ", ".join(labels)


def format_audience_label(row: dict) -> str:
    teachers = row.get("audience_teachers", True)
    students = row.get("audience_students", True)
    parents = row.get("audience_parents", True)
    if teachers and students and parents:
        return "All"
    parts = []
    if teachers:
        parts.append("Teachers")
    if students:
        parts.append("Students")
    if parents:
        parts.append("Parents")
    return ", ".join(parts) if parts else "—"


def list_announcements(school_id: str, limit=50, role=None):
    try:
        query = (
            supabase_admin.table("announcements")
            .select("*")
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        column = _ROLE_COLUMN.get(role)
        if column:
            query = query.eq(column, True)
        result = query.execute()
        return result.data or []
    except Exception:
        return []


def create_announcement(
    school_id: str,
    author_id: str,
    title: str,
    body: str,
    *,
    audience_teachers: bool = True,
    audience_students: bool = True,
    audience_parents: bool = True,
):
    payload = {
        "school_id": school_id,
        "author_id": author_id,
        "title": title.strip(),
        "body": (body or "").strip() or None,
        "audience_teachers": audience_teachers,
        "audience_students": audience_students,
        "audience_parents": audience_parents,
    }
    try:
        result = supabase_admin.table("announcements").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        payload.pop("audience_teachers", None)
        payload.pop("audience_students", None)
        payload.pop("audience_parents", None)
        try:
            result = supabase_admin.table("announcements").insert(payload).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None


def _audience_role_for_user(role: str):
    if role in ("school_admin", "accountant"):
        return None
    return {"teacher": "teacher", "student": "student", "parent": "parent"}.get(role)


def get_read_set(user_id: str) -> set:
    try:
        rows = (
            supabase_admin.table("announcement_reads")
            .select("announcement_id, announcement_type")
            .eq("user_id", user_id)
            .execute()
            .data or []
        )
        return {(r["announcement_type"], r["announcement_id"]) for r in rows}
    except Exception:
        return set()


def mark_announcement_read(user_id: str, announcement_id: str, announcement_type: str = "school") -> bool:
    if announcement_type not in ("school", "class"):
        return False
    try:
        supabase_admin.table("announcement_reads").upsert(
            {
                "user_id": user_id,
                "announcement_id": announcement_id,
                "announcement_type": announcement_type,
            },
            on_conflict="user_id,announcement_id,announcement_type",
        ).execute()
        return True
    except Exception:
        try:
            supabase_admin.table("announcement_reads").insert(
                {
                    "user_id": user_id,
                    "announcement_id": announcement_id,
                    "announcement_type": announcement_type,
                }
            ).execute()
            return True
        except Exception:
            return False


def mark_all_announcements_read(user_id: str, items: list) -> None:
    for item in items:
        mark_announcement_read(user_id, item["id"], item.get("type", "school"))


def _class_announcements_for_teacher(teacher_id: str, school_id: str, limit=30):
    try:
        return (
            supabase_admin.table("class_announcements")
            .select("*")
            .eq("teacher_id", teacher_id)
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []


def _class_announcements_for_student(student: dict, school_id: str, limit=30):
    class_id = student.get("class_id") if student else None
    try:
        rows = (
            supabase_admin.table("class_announcements")
            .select("*")
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit * 2)
            .execute()
            .data or []
        )
        if class_id:
            rows = [r for r in rows if not r.get("class_id") or r["class_id"] == class_id]
        return rows[:limit]
    except Exception:
        return []


def _format_unread_item(row: dict, announcement_type: str, label: str = "School"):
    body = (row.get("body") or "").strip()
    created = row.get("created_at") or ""
    return {
        "id": row["id"],
        "type": announcement_type,
        "title": row.get("title") or "Announcement",
        "body": body[:120] + ("…" if len(body) > 120 else ""),
        "created_at": created[:10] if created else "",
        "sort_at": created,
        "label": label,
    }


def _strip_sort_key(items: list) -> list:
    return [{k: v for k, v in item.items() if k != "sort_at"} for item in items]


def get_unread_announcements(user_id: str, school_id: str, role: str, limit=20) -> list:
    read = get_read_set(user_id)
    items = []

    if role == "student":
        from models.student_model import get_student_by_user_id
        from models.student_portal_model import get_merged_announcements_for_student

        student = get_student_by_user_id(user_id, school_id)
        if student:
            for row in get_merged_announcements_for_student(student, school_id, limit=50):
                ann_type = row.get("announcement_type", "school")
                if (ann_type, row["id"]) not in read:
                    items.append(_format_unread_item(
                        row, ann_type, row.get("type_label", "School")
                    ))
    else:
        audience = _audience_role_for_user(role)

        if audience is not None or role in ("school_admin", "accountant"):
            for row in list_announcements(school_id, limit=50, role=audience):
                if ("school", row["id"]) not in read:
                    items.append(_format_unread_item(row, "school", "School"))

        if role == "teacher":
            from models.teacher_model import get_teacher_by_user_id

            teacher = get_teacher_by_user_id(user_id, school_id)
            if teacher:
                for row in _class_announcements_for_teacher(teacher["id"], school_id):
                    if ("class", row["id"]) not in read:
                        items.append(_format_unread_item(row, "class", "Class"))

    items.sort(key=lambda x: x.get("sort_at") or "", reverse=True)
    return _strip_sort_key(items[:limit])


def get_unread_count(user_id: str, school_id: str, role: str) -> int:
    return len(get_unread_announcements(user_id, school_id, role, limit=100))


def announcements_list_url_for_role(role: str) -> str:
    from flask import url_for

    routes = {
        "school_admin": "announcements.index",
        "accountant": "fees.index",
        "teacher": "teacher_portal.announcements",
        "student": "student_portal.announcements",
        "parent": "parent_portal.announcements",
    }
    endpoint = routes.get(role)
    return url_for(endpoint) if endpoint else url_for("dashboard.index")
