from datetime import datetime, timezone
from models.supabase_client import supabase_admin

STAFF_STATUSES = ["active", "inactive", "on_leave", "terminated"]
DESIGNATIONS = ["Teacher", "Senior Teacher", "Head of Department", "Lab Assistant", "Librarian", "Coordinator", "Other"]
DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_subjects(school_id: str):
    try:
        result = (
            supabase_admin.table("subjects")
            .select("*")
            .eq("school_id", school_id)
            .order("name")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def get_or_create_subject(school_id: str, name: str):
    name = name.strip()
    if not name:
        return None
    existing = (
        supabase_admin.table("subjects")
        .select("id")
        .eq("school_id", school_id)
        .eq("name", name)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return existing[0]["id"]
    result = supabase_admin.table("subjects").insert({"school_id": school_id, "name": name}).execute()
    return result.data[0]["id"] if result.data else None


def get_classes(school_id: str):
    try:
        result = (
            supabase_admin.table("classes")
            .select("id, name, grade, section")
            .eq("school_id", school_id)
            .order("grade")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def search_teachers(school_id: str, query=None, status=None):
    try:
        q = (
            supabase_admin.table("teachers")
            .select("*")
            .eq("school_id", school_id)
            .order("full_name")
        )
        if query:
            term = query.strip()
            q = q.or_(
                f"full_name.ilike.%{term}%,"
                f"employee_id.ilike.%{term}%,"
                f"email.ilike.%{term}%,"
                f"phone.ilike.%{term}%"
            )
        if status:
            q = q.eq("status", status)
        result = q.execute()
        return result.data or []
    except Exception:
        return []


def get_teacher_by_id(teacher_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("teachers")
            .select("*")
            .eq("id", teacher_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def get_teacher_by_user_id(user_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("teachers")
            .select("*")
            .eq("user_id", user_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def teacher_owns_class(teacher_id: str, class_id: str) -> bool:
    if not class_id:
        return False
    return class_id in get_assigned_class_ids(teacher_id)


def get_assigned_subjects(teacher_id: str):
    try:
        links = (
            supabase_admin.table("teacher_subjects")
            .select("subject_id")
            .eq("teacher_id", teacher_id)
            .execute()
            .data or []
        )
        if not links:
            return []
        ids = [l["subject_id"] for l in links]
        return (
            supabase_admin.table("subjects")
            .select("*")
            .in_("id", ids)
            .execute()
            .data or []
        )
    except Exception:
        return []


def get_assigned_classes(teacher_id: str):
    try:
        links = (
            supabase_admin.table("teacher_classes")
            .select("class_id")
            .eq("teacher_id", teacher_id)
            .execute()
            .data or []
        )
        if not links:
            return []
        ids = [l["class_id"] for l in links]
        return (
            supabase_admin.table("classes")
            .select("*")
            .in_("id", ids)
            .execute()
            .data or []
        )
    except Exception:
        return []


def get_timetable(teacher_id: str):
    try:
        rows = (
            supabase_admin.table("teacher_timetable")
            .select("*")
            .eq("teacher_id", teacher_id)
            .order("day_of_week")
            .execute()
            .data or []
        )
        class_ids = {r["class_id"] for r in rows if r.get("class_id")}
        subject_ids = {r["subject_id"] for r in rows if r.get("subject_id")}
        class_map = {}
        subject_map = {}
        if class_ids:
            classes = supabase_admin.table("classes").select("id, name, grade, section").in_("id", list(class_ids)).execute().data or []
            class_map = {c["id"]: c for c in classes}
        if subject_ids:
            subjects = supabase_admin.table("subjects").select("id, name").in_("id", list(subject_ids)).execute().data or []
            subject_map = {s["id"]: s for s in subjects}
        for row in rows:
            row["class_info"] = class_map.get(row.get("class_id"))
            row["subject_info"] = subject_map.get(row.get("subject_id"))
        return rows
    except Exception:
        return []


def get_attendance(teacher_id: str, limit=30):
    try:
        result = (
            supabase_admin.table("teacher_attendance")
            .select("*")
            .eq("teacher_id", teacher_id)
            .order("date", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def _sync_links(table: str, teacher_id: str, school_id: str, ids: list, id_column: str):
    existing = (
        supabase_admin.table(table)
        .select(id_column)
        .eq("teacher_id", teacher_id)
        .execute()
        .data or []
    )
    existing_ids = {r[id_column] for r in existing}
    new_ids = set(ids)

    for rid in existing_ids - new_ids:
        supabase_admin.table(table).delete().eq("teacher_id", teacher_id).eq(id_column, rid).execute()

    for rid in new_ids - existing_ids:
        supabase_admin.table(table).insert({
            "teacher_id": teacher_id,
            id_column: rid,
            "school_id": school_id,
        }).execute()


def create_teacher(school_id: str, data: dict, subject_ids: list = None, class_ids: list = None, new_subjects: list = None):
    for name in (new_subjects or []):
        sid = get_or_create_subject(school_id, name)
        if sid and sid not in (subject_ids or []):
            subject_ids = (subject_ids or []) + [sid]

    payload = {
        "school_id": school_id,
        "full_name": data["full_name"].strip(),
        "employee_id": data["employee_id"].strip(),
        "phone": (data.get("phone") or "").strip() or None,
        "email": (data.get("email") or "").strip() or None,
        "cnic": (data.get("cnic") or "").strip() or None,
        "qualification": (data.get("qualification") or "").strip() or None,
        "joining_date": data.get("joining_date") or None,
        "designation": (data.get("designation") or "Teacher").strip(),
        "status": data.get("status") or "active",
        "updated_at": _now_iso(),
    }
    result = supabase_admin.table("teachers").insert(payload).execute()
    teacher = result.data[0]

    if subject_ids:
        _sync_links("teacher_subjects", teacher["id"], school_id, subject_ids, "subject_id")
    if class_ids:
        _sync_links("teacher_classes", teacher["id"], school_id, class_ids, "class_id")

    return teacher


def update_teacher(teacher_id: str, school_id: str, data: dict, subject_ids: list = None, class_ids: list = None, new_subjects: list = None):
    existing = get_teacher_by_id(teacher_id, school_id)
    if not existing:
        return None

    if new_subjects:
        subject_ids = list(subject_ids or [])
        for name in new_subjects:
            sid = get_or_create_subject(school_id, name)
            if sid and sid not in subject_ids:
                subject_ids.append(sid)

    payload = {
        "full_name": data["full_name"].strip(),
        "employee_id": data["employee_id"].strip(),
        "phone": (data.get("phone") or "").strip() or None,
        "email": (data.get("email") or "").strip() or None,
        "cnic": (data.get("cnic") or "").strip() or None,
        "qualification": (data.get("qualification") or "").strip() or None,
        "joining_date": data.get("joining_date") or None,
        "designation": (data.get("designation") or "Teacher").strip(),
        "status": data.get("status") or existing.get("status", "active"),
        "updated_at": _now_iso(),
    }

    result = (
        supabase_admin.table("teachers")
        .update(payload)
        .eq("id", teacher_id)
        .eq("school_id", school_id)
        .execute()
    )
    teacher = result.data[0] if result.data else None

    if teacher and subject_ids is not None:
        _sync_links("teacher_subjects", teacher_id, school_id, subject_ids, "subject_id")
    if teacher and class_ids is not None:
        _sync_links("teacher_classes", teacher_id, school_id, class_ids, "class_id")

    return teacher


def deactivate_teacher(teacher_id: str, school_id: str):
    result = (
        supabase_admin.table("teachers")
        .update({"status": "inactive", "updated_at": _now_iso()})
        .eq("id", teacher_id)
        .eq("school_id", school_id)
        .execute()
    )
    return result.data[0] if result.data else None


def delete_teacher(teacher_id: str, school_id: str):
    result = (
        supabase_admin.table("teachers")
        .delete()
        .eq("id", teacher_id)
        .eq("school_id", school_id)
        .execute()
    )
    return bool(result.data)


def add_timetable_slot(teacher_id: str, school_id: str, data: dict):
    payload = {
        "teacher_id": teacher_id,
        "school_id": school_id,
        "class_id": data.get("class_id") or None,
        "subject_id": data.get("subject_id") or None,
        "day_of_week": data["day_of_week"],
        "start_time": data["start_time"],
        "end_time": data["end_time"],
        "room": (data.get("room") or "").strip() or None,
    }
    result = supabase_admin.table("teacher_timetable").insert(payload).execute()
    return result.data[0] if result.data else None


def record_attendance(teacher_id: str, school_id: str, data: dict):
    payload = {
        "teacher_id": teacher_id,
        "school_id": school_id,
        "date": data["date"],
        "status": data.get("status") or "present",
        "check_in": data.get("check_in") or None,
        "check_out": data.get("check_out") or None,
        "notes": (data.get("notes") or "").strip() or None,
    }
    result = supabase_admin.table("teacher_attendance").upsert(payload, on_conflict="teacher_id,date").execute()
    return result.data[0] if result.data else None


def get_assigned_subject_ids(teacher_id: str):
    try:
        rows = supabase_admin.table("teacher_subjects").select("subject_id").eq("teacher_id", teacher_id).execute().data or []
        return [r["subject_id"] for r in rows]
    except Exception:
        return []


def get_assigned_class_ids(teacher_id: str):
    try:
        rows = supabase_admin.table("teacher_classes").select("class_id").eq("teacher_id", teacher_id).execute().data or []
        return [r["class_id"] for r in rows]
    except Exception:
        return []


def enable_teacher_login(teacher_id: str, school_id: str, email: str, password: str, full_name: str):
    teacher = get_teacher_by_id(teacher_id, school_id)
    if not teacher:
        return None, "Teacher not found."
    if teacher.get("user_id"):
        return None, "Login already enabled."
    if not email:
        return None, "Email is required."

    try:
        auth_user = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
        })
        user_id = auth_user.user.id
        supabase_admin.table("user_profiles").insert({
            "id": user_id,
            "full_name": full_name,
            "role": "teacher",
            "school_id": school_id,
            "phone": teacher.get("phone"),
            "is_active": True,
        }).execute()
        result = (
            supabase_admin.table("teachers")
            .update({"user_id": user_id, "email": email, "login_enabled": True, "updated_at": _now_iso()})
            .eq("id", teacher_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as e:
        err = str(e)
        if "already" in err.lower():
            return None, "Email already registered."
        return None, "Could not create login account."


def reset_teacher_password(teacher_id: str, school_id: str, new_password: str):
    teacher = get_teacher_by_id(teacher_id, school_id)
    if not teacher or not teacher.get("user_id"):
        return False, "No login linked."
    try:
        supabase_admin.auth.admin.update_user_by_id(teacher["user_id"], {"password": new_password})
        return True, None
    except Exception:
        return False, "Password reset failed."
