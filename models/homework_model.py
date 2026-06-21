import uuid
from datetime import date, datetime, timezone
from models.supabase_client import supabase_admin

HOMEWORK_BUCKET = "homework-attachments"
HW_TYPES = [("homework", "Homework"), ("classwork", "Classwork")]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def upload_file(school_id: str, folder: str, file_bytes: bytes, filename: str, content_type: str):
    safe_name = filename.replace(" ", "_")
    path = f"{school_id}/{folder}/{uuid.uuid4().hex}_{safe_name}"
    try:
        supabase_admin.storage.from_(HOMEWORK_BUCKET).upload(
            path,
            file_bytes,
            {"content-type": content_type or "application/octet-stream", "upsert": "true"},
        )
        return supabase_admin.storage.from_(HOMEWORK_BUCKET).get_public_url(path)
    except Exception:
        return None


def _enrich_homework_rows(rows: list, school_id: str, student_id: str = None):
    if not rows:
        return []

    class_ids = {r["class_id"] for r in rows if r.get("class_id")}
    subject_ids = {r["subject_id"] for r in rows if r.get("subject_id")}
    class_map = {}
    subject_map = {}
    if class_ids:
        classes = supabase_admin.table("classes").select("id, name, grade, section").in_("id", list(class_ids)).execute().data or []
        class_map = {c["id"]: c for c in classes}
    if subject_ids:
        subjects = supabase_admin.table("subjects").select("id, name").in_("id", list(subject_ids)).execute().data or []
        subject_map = {s["id"]: s["name"] for s in subjects}

    hw_ids = [r["id"] for r in rows]
    submission_counts = {}
    views_map = {}
    submissions_map = {}

    if hw_ids:
        try:
            subs = supabase_admin.table("homework_submissions").select("homework_id, student_id, status, submitted_at, teacher_comment").in_("homework_id", hw_ids).execute().data or []
            for s in subs:
                if s.get("submitted_at"):
                    submission_counts[s["homework_id"]] = submission_counts.get(s["homework_id"], 0) + 1
                if student_id and s["student_id"] == student_id:
                    submissions_map[s["homework_id"]] = s
        except Exception:
            pass

        if student_id:
            try:
                views = supabase_admin.table("homework_views").select("homework_id, viewed_at").eq("student_id", student_id).in_("homework_id", hw_ids).execute().data or []
                views_map = {v["homework_id"]: v for v in views}
            except Exception:
                pass

    today = date.today().isoformat()
    enriched = []
    for row in rows:
        cls = class_map.get(row.get("class_id"), {})
        sub = submissions_map.get(row["id"])
        view = views_map.get(row["id"])
        due = row.get("due_date") or ""
        has_submitted = bool(sub and sub.get("submitted_at"))
        enriched.append({
            **row,
            "class_label": cls.get("name") or cls.get("grade") or row.get("class_grade") or "—",
            "section": cls.get("section") or row.get("section"),
            "subject_name": subject_map.get(row.get("subject_id"), "General"),
            "submission_count": submission_counts.get(row["id"], 0),
            "submitted": has_submitted if student_id else None,
            "submission_status": sub.get("status") if sub and has_submitted else None,
            "submitted_at": sub.get("submitted_at") if sub else None,
            "teacher_comment": sub.get("teacher_comment") if sub else None,
            "seen": bool(view),
            "seen_at": view.get("viewed_at") if view else None,
            "is_overdue": bool(due and due < today and not has_submitted) if student_id else False,
            "hw_type_label": (row.get("hw_type") or "homework").replace("_", " ").title(),
        })
    return enriched


def create_homework(school_id: str, teacher_id: str, user_id: str, data: dict, attachment_url: str = None, attachment_name: str = None):
    cls = None
    if data.get("class_id"):
        classes = supabase_admin.table("classes").select("grade, section").eq("id", data["class_id"]).limit(1).execute().data or []
        cls = classes[0] if classes else None

    payload = {
        "school_id": school_id,
        "teacher_id": teacher_id,
        "class_id": data.get("class_id") or None,
        "class_grade": cls.get("grade") if cls else data.get("class_grade"),
        "section": cls.get("section") if cls else data.get("section"),
        "subject_id": data.get("subject_id") or None,
        "title": data["title"].strip(),
        "description": (data.get("description") or "").strip() or None,
        "due_date": data.get("due_date") or None,
        "assigned_date": date.today().isoformat(),
        "created_by": user_id,
        "hw_type": data.get("hw_type") or "homework",
        "submission_enabled": data.get("submission_enabled", True),
        "attachment_url": attachment_url,
        "attachment_name": attachment_name,
    }
    try:
        result = supabase_admin.table("homework_assignments").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_homework_by_id(homework_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("homework_assignments")
            .select("*")
            .eq("id", homework_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def get_teacher_homework(teacher_id: str, school_id: str, user_id: str = None, limit=50):
    try:
        rows = (
            supabase_admin.table("homework_assignments")
            .select("*")
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit * 2)
            .execute()
            .data or []
        )
    except Exception:
        return []

    from models.teacher_model import get_assigned_class_ids
    class_ids = set(get_assigned_class_ids(teacher_id))
    filtered = [
        r for r in rows
        if r.get("teacher_id") == teacher_id
        or r.get("created_by") == user_id
        or (r.get("class_id") and r["class_id"] in class_ids)
    ]
    return _enrich_homework_rows(filtered[:limit], school_id)


def _match_homework_for_student(row: dict, student: dict) -> bool:
    if student.get("class_id") and row.get("class_id") == student["class_id"]:
        return True
    if row.get("class_grade") == student.get("class_grade"):
        if not row.get("section") or row.get("section") == student.get("section"):
            return True
    return False


def get_homework_for_student(student: dict, school_id: str, limit=30):
    try:
        rows = (
            supabase_admin.table("homework_assignments")
            .select("*")
            .eq("school_id", school_id)
            .order("due_date", desc=True)
            .limit(limit * 3)
            .execute()
            .data or []
        )
    except Exception:
        return []

    matched = [r for r in rows if _match_homework_for_student(r, student)][:limit]
    return _enrich_homework_rows(matched, school_id, student["id"])


def get_homework_for_students(students: list, school_id: str, limit=30):
    if not students:
        return []
    seen_ids = set()
    all_hw = []
    for student in students:
        for hw in get_homework_for_student(student, school_id, limit=limit):
            if hw["id"] not in seen_ids:
                seen_ids.add(hw["id"])
                all_hw.append({**hw, "child_name": student.get("full_name"), "student_id": student["id"]})
    all_hw.sort(key=lambda h: h.get("due_date") or "", reverse=True)
    return all_hw[:limit]


def mark_homework_seen(homework_id: str, student_id: str, school_id: str, viewed_by: str = None):
    payload = {
        "school_id": school_id,
        "homework_id": homework_id,
        "student_id": student_id,
        "viewed_by": viewed_by,
        "viewed_at": _now_iso(),
    }
    try:
        supabase_admin.table("homework_views").upsert(payload, on_conflict="homework_id,student_id").execute()
        return True
    except Exception:
        return False


def get_homework_submission(homework_id: str, student_id: str, school_id: str):
    try:
        rows = (
            supabase_admin.table("homework_submissions")
            .select("*")
            .eq("homework_id", homework_id)
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .limit(1)
            .execute()
            .data or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def submit_homework(homework_id: str, student_id: str, school_id: str, notes: str = None,
                    attachment_url: str = None, attachment_name: str = None):
    hw = get_homework_by_id(homework_id, school_id)
    if not hw:
        return None, "Homework not found."
    if not hw.get("submission_enabled", True):
        return None, "Submission is not enabled for this assignment."

    today = date.today().isoformat()
    due = hw.get("due_date") or today
    status = "late" if due < today else "submitted"

    payload = {
        "school_id": school_id,
        "homework_id": homework_id,
        "student_id": student_id,
        "status": status,
        "notes": (notes or "").strip() or None,
        "attachment_url": attachment_url,
        "attachment_name": attachment_name,
        "submitted_at": _now_iso(),
        "seen_at": _now_iso(),
    }
    try:
        result = supabase_admin.table("homework_submissions").upsert(
            payload, on_conflict="homework_id,student_id"
        ).execute()
        mark_homework_seen(homework_id, student_id, school_id)
        return result.data[0] if result.data else None, None
    except Exception:
        return None, "Could not submit homework."


def get_homework_submissions(homework_id: str, school_id: str):
    try:
        rows = (
            supabase_admin.table("homework_submissions")
            .select("*")
            .eq("homework_id", homework_id)
            .eq("school_id", school_id)
            .order("submitted_at", desc=True)
            .execute()
            .data or []
        )
    except Exception:
        return []

    if not rows:
        return []

    student_ids = {r["student_id"] for r in rows}
    students = (
        supabase_admin.table("students")
        .select("id, full_name, roll_number")
        .in_("id", list(student_ids))
        .execute()
        .data or []
    )
    smap = {s["id"]: s for s in students}

    view_rows = (
        supabase_admin.table("homework_views")
        .select("student_id, viewed_at")
        .eq("homework_id", homework_id)
        .execute()
        .data or []
    )
    vmap = {v["student_id"]: v for v in view_rows}

    result = []
    for row in rows:
        if row.get("status") == "missing" and not row.get("notes") and not row.get("submitted_at"):
            continue
        result.append({
            **row,
            "student": smap.get(row["student_id"], {}),
            "seen_at": row.get("seen_at") or vmap.get(row["student_id"], {}).get("viewed_at"),
        })
    return result


def get_homework_views(homework_id: str, school_id: str):
    try:
        rows = (
            supabase_admin.table("homework_views")
            .select("*")
            .eq("homework_id", homework_id)
            .eq("school_id", school_id)
            .execute()
            .data or []
        )
    except Exception:
        return []
    student_ids = {r["student_id"] for r in rows}
    if not student_ids:
        return rows
    students = supabase_admin.table("students").select("id, full_name, roll_number").in_("id", list(student_ids)).execute().data or []
    smap = {s["id"]: s for s in students}
    return [{**r, "student": smap.get(r["student_id"], {})} for r in rows]


def record_teacher_submission(homework_id: str, school_id: str, student_id: str, notes: str = None, status: str = "submitted"):
    payload = {
        "school_id": school_id,
        "homework_id": homework_id,
        "student_id": student_id,
        "status": status,
        "notes": notes,
        "submitted_at": _now_iso(),
    }
    try:
        result = supabase_admin.table("homework_submissions").upsert(
            payload, on_conflict="homework_id,student_id"
        ).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def add_teacher_comment(homework_id: str, student_id: str, school_id: str, comment: str):
    try:
        result = (
            supabase_admin.table("homework_submissions")
            .update({"teacher_comment": comment.strip(), "status": "graded"})
            .eq("homework_id", homework_id)
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .execute()
        )
        return bool(result.data)
    except Exception:
        return False
