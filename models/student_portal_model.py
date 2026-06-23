from datetime import date, datetime, timezone
from calendar import monthrange
from models.supabase_client import supabase_admin
from models.parent_portal_model import (
    get_attendance_summary,
    get_daily_attendance,
    get_monthly_attendance,
    get_class_timetable,
    get_announcements,
)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _today_day_name():
    return date.today().strftime("%A").lower()


def get_dashboard_data(student: dict, school_id: str):
    sid = student["id"]
    attendance = get_attendance_summary(sid, school_id)
    homework = get_homework_for_student(student, school_id, limit=5)
    pending_hw = count_pending_homework(student, school_id)
    results = get_exam_results(sid, school_id, limit=3)
    latest_result = results[0] if results else None
    upcoming_exams = get_upcoming_exams(student, school_id, limit=5)
    announcements = get_announcements(school_id, limit=5, role="student")
    class_ann = get_class_announcements_for_student(student, school_id, limit=5)
    merged_announcements = get_merged_announcements_for_student(student, school_id, limit=5)
    timetable = get_class_timetable(student.get("class_id"), school_id)
    todays_schedule = [s for s in timetable if s.get("day_of_week") == _today_day_name()]
    subjects = get_subjects_for_student(student, school_id)
    fees = get_fee_summary(student, school_id)
    notifications = get_notifications(sid, limit=5)

    return {
        "attendance_summary": attendance,
        "homework_list": homework,
        "pending_homework_count": pending_hw,
        "latest_result": latest_result,
        "recent_results": results,
        "upcoming_exams": upcoming_exams,
        "announcements": announcements,
        "class_announcements": class_ann,
        "merged_announcements": merged_announcements,
        "todays_schedule": todays_schedule,
        "subjects": subjects,
        "subject_count": len(subjects),
        "fee_summary": fees,
        "notifications": notifications,
    }


def get_homework_for_student(student: dict, school_id: str, limit=30):
    from models.homework_model import get_homework_for_student as _get
    return _get(student, school_id, limit)


def count_pending_homework(student: dict, school_id: str) -> int:
    hw = get_homework_for_student(student, school_id, limit=50)
    return sum(1 for h in hw if not h.get("submitted") and not h.get("is_overdue")) + sum(
        1 for h in hw if h.get("is_overdue") and not h.get("submitted")
    )


def get_homework_by_id(homework_id: str, school_id: str):
    from models.homework_model import get_homework_by_id as _get
    return _get(homework_id, school_id)


def get_homework_submission(homework_id: str, student_id: str, school_id: str):
    from models.homework_model import get_homework_submission as _get
    return _get(homework_id, student_id, school_id)


def submit_homework(homework_id: str, student_id: str, school_id: str, notes: str = None):
    from models.homework_model import submit_homework as _submit
    return _submit(homework_id, student_id, school_id, notes)


def get_exam_results(student_id: str, school_id: str, limit=30):
    results = _get_legacy_exam_results(student_id, school_id, limit)
    term_results = _get_published_term_results(student_id, school_id, limit)
    combined = term_results + results
    return combined[:limit]


def _get_legacy_exam_results(student_id: str, school_id: str, limit=30):
    try:
        rows = (
            supabase_admin.table("exam_results")
            .select("*")
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []

    exam_ids = {r["exam_id"] for r in rows}
    exam_map = {}
    if exam_ids:
        exams = (
            supabase_admin.table("exams")
            .select("id, title, exam_date, class_id")
            .in_("id", list(exam_ids))
            .execute()
            .data or []
        )
        exam_map = {e["id"]: e for e in exams}

    enriched = []
    for row in rows:
        exam = exam_map.get(row["exam_id"], {})
        enriched.append({**row, "exam": exam, "exam_title": exam.get("title", "Exam")})
    return enriched


def _get_published_term_results(student_id: str, school_id: str, limit=20):
    try:
        from models.exam_model import get_student_result_history, get_student_subject_marks
        history = get_student_result_history(student_id, school_id, published_only=True)[:limit]
    except Exception:
        return []

    enriched = []
    for row in history:
        term = row.get("term") or {}
        subjects = get_student_subject_marks(row["exam_term_id"], student_id, school_id)
        enriched.append({
            "id": row["id"],
            "exam_id": row["exam_term_id"],
            "student_id": student_id,
            "marks_obtained": row.get("total_obtained"),
            "max_marks": row.get("total_max"),
            "grade": row.get("overall_grade"),
            "remarks": f"Rank #{row.get('class_rank') or '—'}",
            "exam": term,
            "exam_title": term.get("name", "Exam Term"),
            "is_term_result": True,
            "percentage": row.get("percentage"),
            "subjects": subjects,
        })
    return enriched


def get_grade_summary(student_id: str, school_id: str):
    results = get_exam_results(student_id, school_id, limit=100)
    if not results:
        return {"average_pct": 0, "total_exams": 0, "highest": None, "lowest": None}

    pcts = []
    for r in results:
        if r.get("is_term_result"):
            pcts.append(float(r.get("percentage") or 0))
            continue
        max_m = float(r.get("max_marks") or 100)
        marks = float(r.get("marks_obtained") or 0)
        if max_m > 0:
            pcts.append((marks / max_m) * 100)

    avg = round(sum(pcts) / len(pcts)) if pcts else 0
    return {
        "average_pct": avg,
        "total_exams": len(results),
        "highest": max(pcts) if pcts else None,
        "lowest": min(pcts) if pcts else None,
    }


def get_upcoming_exams(student: dict, school_id: str, limit=10):
    class_id = student.get("class_id")
    today = date.today().isoformat()
    try:
        q = (
            supabase_admin.table("exams")
            .select("*")
            .eq("school_id", school_id)
            .gte("exam_date", today)
            .order("exam_date")
            .limit(limit * 2)
        )
        rows = q.execute().data or []
        if class_id:
            rows = [r for r in rows if not r.get("class_id") or r["class_id"] == class_id]
        return rows[:limit]
    except Exception:
        return []


def get_class_announcements_for_student(student: dict, school_id: str, limit=20):
    class_id = student.get("class_id")
    try:
        q = (
            supabase_admin.table("class_announcements")
            .select("*")
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit * 2)
        )
        rows = q.execute().data or []
        if class_id:
            rows = [r for r in rows if not r.get("class_id") or r["class_id"] == class_id]
        return rows[:limit]
    except Exception:
        return []


def get_merged_announcements_for_student(student: dict, school_id: str, limit=20):
    """School + class announcements merged, newest first."""
    school = [
        {**a, "announcement_type": "school", "type_label": "School"}
        for a in get_announcements(school_id, limit=limit, role="student")
    ]
    classroom = [
        {**a, "announcement_type": "class", "type_label": "Class"}
        for a in get_class_announcements_for_student(student, school_id, limit=limit)
    ]
    merged = school + classroom
    merged.sort(key=lambda a: a.get("created_at") or "", reverse=True)
    return merged[:limit]


def get_subjects_for_student(student: dict, school_id: str):
    class_id = student.get("class_id")
    if not class_id:
        return []
    try:
        from models.class_model import get_class_subjects
        assigned = get_class_subjects(class_id, school_id)
        if assigned:
            return assigned

        slots = (
            supabase_admin.table("teacher_timetable")
            .select("subject_id")
            .eq("school_id", school_id)
            .eq("class_id", class_id)
            .execute()
            .data or []
        )
        subject_ids = list({s["subject_id"] for s in slots if s.get("subject_id")})
        if not subject_ids:
            return []
        return (
            supabase_admin.table("subjects")
            .select("*")
            .in_("id", subject_ids)
            .order("name")
            .execute()
            .data or []
        )
    except Exception:
        return []


def get_fee_summary(student: dict, school_id: str):
    lookup_ids = [student["id"]]
    if student.get("user_id"):
        lookup_ids.append(student["user_id"])
    try:
        rows = (
            supabase_admin.table("fee_records")
            .select("*")
            .eq("school_id", school_id)
            .in_("student_id", lookup_ids)
            .execute()
            .data or []
        )
    except Exception:
        return {"total_due": 0, "total_paid": 0, "records": [], "status": "clear"}

    from models.fee_model import enrich_fee_record

    total_due = 0.0
    total_paid = 0.0
    has_pending = False
    enriched = []
    for row in rows:
        if row.get("is_void"):
            continue
        fee = enrich_fee_record(row)
        enriched.append(fee)
        amount = float(fee.get("total_amount") or fee.get("amount") or 0)
        paid = float(fee.get("amount_paid") or 0)
        total_paid += paid
        balance = fee.get("balance") or max(amount - paid, 0)
        if fee.get("status") in ("pending", "partial", "overdue") and balance > 0:
            total_due += balance
            has_pending = True

    return {
        "total_due": total_due,
        "total_paid": total_paid,
        "records": enriched,
        "status": "pending" if has_pending else "clear",
    }


def get_study_materials(student: dict, school_id: str, limit=30):
    class_id = student.get("class_id")
    try:
        q = (
            supabase_admin.table("study_materials")
            .select("*")
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit * 2)
        )
        rows = q.execute().data or []
        if class_id:
            rows = [r for r in rows if not r.get("class_id") or r["class_id"] == class_id]
    except Exception:
        return []

    subject_ids = {r["subject_id"] for r in rows if r.get("subject_id")}
    subject_map = {}
    if subject_ids:
        subjects = supabase_admin.table("subjects").select("id, name").in_("id", list(subject_ids)).execute().data or []
        subject_map = {s["id"]: s["name"] for s in subjects}

    for row in rows[:limit]:
        row["subject_name"] = subject_map.get(row.get("subject_id"), "General")
    return rows[:limit]


def get_notifications(student_id: str, limit=20):
    try:
        return (
            supabase_admin.table("student_notifications")
            .select("*")
            .eq("student_id", student_id)
            .order("sent_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []


def get_student_messages(student_id: str, school_id: str, limit=30):
    try:
        return (
            supabase_admin.table("student_messages")
            .select("*")
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []


def send_student_message(student_id: str, school_id: str, subject: str, message: str):
    payload = {
        "student_id": student_id,
        "school_id": school_id,
        "subject": subject.strip(),
        "message": message.strip(),
        "status": "open",
    }
    try:
        result = supabase_admin.table("student_messages").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None
