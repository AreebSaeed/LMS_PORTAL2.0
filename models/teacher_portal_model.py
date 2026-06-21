from datetime import date, datetime, timezone
from models.supabase_client import supabase_admin
from models.teacher_model import (
    get_assigned_classes, get_assigned_subjects, get_timetable,
    get_assigned_class_ids,
)
from models.attendance_model import get_students_for_class, is_sheet_submitted


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _today_day_name():
    return date.today().strftime("%A").lower()


def get_dashboard_data(teacher_id: str, school_id: str, user_id: str):
    classes = get_assigned_classes(teacher_id)
    subjects = get_assigned_subjects(teacher_id)
    timetable = get_timetable(teacher_id)
    today = date.today().isoformat()
    day_name = _today_day_name()

    todays_classes = [s for s in timetable if s.get("day_of_week") == day_name]
    attendance_pending = get_attendance_pending(teacher_id, school_id, today)
    homework_list = get_teacher_homework(teacher_id, school_id, user_id, limit=5)
    upcoming_exams = get_upcoming_exams_for_teacher(teacher_id, school_id, limit=5)
    school_announcements = get_school_announcements(school_id, limit=5)
    class_announcements = get_class_announcements(teacher_id, school_id, limit=5)
    student_count = _count_students(classes, school_id)

    return {
        "classes": classes,
        "subjects": subjects,
        "class_count": len(classes),
        "subject_count": len(subjects),
        "student_count": student_count,
        "todays_classes": todays_classes,
        "attendance_pending": attendance_pending,
        "homework_list": homework_list,
        "upcoming_exams": upcoming_exams,
        "school_announcements": school_announcements,
        "class_announcements": class_announcements,
    }


def _count_students(classes: list, school_id: str) -> int:
    total = 0
    seen = set()
    for cls in classes:
        cid = cls["id"]
        if cid in seen:
            continue
        seen.add(cid)
        students = get_students_for_class(school_id, class_id=cid)
        total += len(students)
    return total


def get_attendance_pending(teacher_id: str, school_id: str, att_date: str):
    pending = []
    for cls in get_assigned_classes(teacher_id):
        class_id = cls["id"]
        submitted = is_sheet_submitted(school_id, att_date, class_id=class_id)
        if not submitted:
            pending.append({
                **cls,
                "class_label": cls.get("name") or cls.get("grade") or "Class",
            })
    return pending


def get_todays_schedule(teacher_id: str):
    day_name = _today_day_name()
    return [s for s in get_timetable(teacher_id) if s.get("day_of_week") == day_name]


def get_teacher_homework(teacher_id: str, school_id: str, user_id: str = None, limit=20):
    from models.homework_model import get_teacher_homework as _get
    return _get(teacher_id, school_id, user_id, limit)


def create_homework(school_id: str, teacher_id: str, user_id: str, data: dict):
    from models.homework_model import create_homework as _create
    return _create(school_id, teacher_id, user_id, data)


def get_homework_by_id(homework_id: str, school_id: str):
    from models.homework_model import get_homework_by_id as _get
    return _get(homework_id, school_id)


def get_homework_submissions(homework_id: str, school_id: str):
    from models.homework_model import get_homework_submissions as _get
    return _get(homework_id, school_id)


def record_homework_submission(homework_id: str, school_id: str, student_id: str, notes: str = None, status: str = "submitted"):
    from models.homework_model import record_teacher_submission as _record
    return _record(homework_id, school_id, student_id, notes, status)


def get_upcoming_exams_for_teacher(teacher_id: str, school_id: str, limit=10):
    class_ids = get_assigned_class_ids(teacher_id)
    if not class_ids:
        return []
    today = date.today().isoformat()
    try:
        rows = (
            supabase_admin.table("exams")
            .select("*")
            .eq("school_id", school_id)
            .in_("class_id", class_ids)
            .gte("exam_date", today)
            .order("exam_date")
            .limit(limit)
            .execute()
            .data or []
        )
        return rows
    except Exception:
        return []


def get_exams_for_teacher(teacher_id: str, school_id: str):
    class_ids = get_assigned_class_ids(teacher_id)
    if not class_ids:
        return []
    try:
        return (
            supabase_admin.table("exams")
            .select("*")
            .eq("school_id", school_id)
            .in_("class_id", class_ids)
            .order("exam_date", desc=True)
            .limit(30)
            .execute()
            .data or []
        )
    except Exception:
        return []


def get_exam_results_for_exam(exam_id: str, school_id: str):
    try:
        rows = (
            supabase_admin.table("exam_results")
            .select("*")
            .eq("exam_id", exam_id)
            .eq("school_id", school_id)
            .execute()
            .data or []
        )
        return {r["student_id"]: r for r in rows}
    except Exception:
        return {}


def save_exam_marks(exam_id: str, school_id: str, marks: dict, max_marks: float = 100):
    saved = 0
    for student_id, data in marks.items():
        marks_val = data.get("marks")
        if marks_val is None or marks_val == "":
            continue
        try:
            marks_num = float(marks_val)
        except (TypeError, ValueError):
            continue
        grade = data.get("grade") or _auto_grade(marks_num, max_marks)
        payload = {
            "school_id": school_id,
            "exam_id": exam_id,
            "student_id": student_id,
            "marks_obtained": marks_num,
            "max_marks": max_marks,
            "grade": grade,
            "remarks": (data.get("remarks") or "").strip() or None,
            "published_at": _now_iso(),
        }
        try:
            supabase_admin.table("exam_results").upsert(
                payload, on_conflict="exam_id,student_id"
            ).execute()
            saved += 1
        except Exception:
            pass
    return saved


def _auto_grade(marks: float, max_marks: float) -> str:
    if max_marks <= 0:
        return "—"
    pct = (marks / max_marks) * 100
    if pct >= 90:
        return "A+"
    if pct >= 80:
        return "A"
    if pct >= 70:
        return "B"
    if pct >= 60:
        return "C"
    if pct >= 50:
        return "D"
    return "F"


def get_school_announcements(school_id: str, limit=10):
    try:
        return (
            supabase_admin.table("announcements")
            .select("*")
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []


def get_class_announcements(teacher_id: str, school_id: str, limit=20):
    try:
        rows = (
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

    class_ids = {r["class_id"] for r in rows if r.get("class_id")}
    class_map = {}
    if class_ids:
        classes = supabase_admin.table("classes").select("id, name, grade, section").in_("id", list(class_ids)).execute().data or []
        class_map = {c["id"]: c for c in classes}

    for row in rows:
        cls = class_map.get(row.get("class_id"), {})
        row["class_label"] = cls.get("name") or cls.get("grade") or "All Classes"
    return rows


def create_class_announcement(teacher_id: str, school_id: str, class_id: str, title: str, body: str):
    payload = {
        "school_id": school_id,
        "teacher_id": teacher_id,
        "class_id": class_id or None,
        "title": title.strip(),
        "body": (body or "").strip() or None,
    }
    try:
        result = supabase_admin.table("class_announcements").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_students_for_teacher_class(teacher_id: str, school_id: str, class_id: str):
    if class_id not in get_assigned_class_ids(teacher_id):
        return []
    return get_students_for_class(school_id, class_id=class_id)
