from datetime import date, datetime, timezone
from calendar import monthrange
from models.supabase_client import supabase_admin

ATTENDANCE_STATUSES = ["present", "absent", "late", "leave"]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


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


def get_teacher_class_ids(teacher_id: str):
    try:
        rows = (
            supabase_admin.table("teacher_classes")
            .select("class_id")
            .eq("teacher_id", teacher_id)
            .execute()
            .data or []
        )
        return [r["class_id"] for r in rows if r.get("class_id")]
    except Exception:
        return []


def get_classes_for_teacher(school_id: str, teacher_id: str):
    class_ids = get_teacher_class_ids(teacher_id)
    if not class_ids:
        return get_all_classes(school_id)
    try:
        result = (
            supabase_admin.table("classes")
            .select("*")
            .eq("school_id", school_id)
            .in_("id", class_ids)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def get_all_classes(school_id: str):
    try:
        result = (
            supabase_admin.table("classes")
            .select("*")
            .eq("school_id", school_id)
            .order("grade")
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def get_students_for_class(school_id: str, class_id: str = None, class_grade: str = None, section: str = None):
    try:
        q = (
            supabase_admin.table("students")
            .select("id, full_name, admission_number, roll_number, class_grade, section, class_id, photo_url, user_id")
            .eq("school_id", school_id)
            .eq("status", "active")
            .order("full_name")
        )
        if class_id:
            q = q.eq("class_id", class_id)
        if class_grade:
            q = q.eq("class_grade", class_grade)
        if section:
            q = q.eq("section", section)
        return q.execute().data or []
    except Exception:
        return []


def get_attendance_for_class_date(school_id: str, att_date: str, class_id: str = None, class_grade: str = None, section: str = None):
    try:
        q = (
            supabase_admin.table("student_attendance")
            .select("*")
            .eq("school_id", school_id)
            .eq("date", att_date)
        )
        if class_id:
            q = q.eq("class_id", class_id)
        elif class_grade:
            q = q.eq("class_grade", class_grade)
            if section:
                q = q.eq("section", section)
        result = q.execute()
        return {r["student_id"]: r for r in (result.data or [])}
    except Exception:
        return {}


def is_sheet_submitted(school_id: str, att_date: str, class_id: str = None, class_grade: str = None, section: str = None):
    records = get_attendance_for_class_date(school_id, att_date, class_id, class_grade, section)
    if not records:
        return False
    return all(r.get("is_submitted") for r in records.values())


def save_class_attendance(school_id: str, att_date: str, marks: dict, marked_by: str, class_id: str = None, class_grade: str = None, section: str = None):
    if is_sheet_submitted(school_id, att_date, class_id, class_grade, section):
        return False, "Attendance already submitted. Contact admin to edit."

    saved = 0
    for student_id, status in marks.items():
        if status not in ATTENDANCE_STATUSES:
            continue
        payload = {
            "school_id": school_id,
            "student_id": student_id,
            "class_id": class_id,
            "class_grade": class_grade,
            "section": section,
            "date": att_date,
            "status": status,
            "marked_by": marked_by,
            "updated_at": _now_iso(),
        }
        try:
            supabase_admin.table("student_attendance").upsert(
                payload, on_conflict="student_id,date"
            ).execute()
            saved += 1
        except Exception:
            pass
    return saved > 0, None


def submit_class_attendance(school_id: str, att_date: str, class_id: str = None, class_grade: str = None, section: str = None):
    try:
        q = (
            supabase_admin.table("student_attendance")
            .update({"is_submitted": True, "submitted_at": _now_iso(), "updated_at": _now_iso()})
            .eq("school_id", school_id)
            .eq("date", att_date)
        )
        if class_id:
            q = q.eq("class_id", class_id)
        elif class_grade:
            q = q.eq("class_grade", class_grade)
            if section:
                q = q.eq("section", section)
        result = q.execute()
        return bool(result.data)
    except Exception:
        return False


def admin_update_attendance(record_id: str, school_id: str, status: str, notes: str = None):
    if status not in ATTENDANCE_STATUSES:
        return None
    payload = {"status": status, "updated_at": _now_iso()}
    if notes is not None:
        payload["notes"] = notes
    try:
        result = (
            supabase_admin.table("student_attendance")
            .update(payload)
            .eq("id", record_id)
            .eq("school_id", school_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_daily_report(school_id: str, att_date: str, class_id: str = None, section: str = None):
    try:
        q = (
            supabase_admin.table("student_attendance")
            .select("*")
            .eq("school_id", school_id)
            .eq("date", att_date)
        )
        if class_id:
            q = q.eq("class_id", class_id)
        if section:
            q = q.eq("section", section)
        rows = q.execute().data or []
        return _enrich_attendance_rows(rows)
    except Exception:
        return []


def get_monthly_report(school_id: str, year: int, month: int, class_id: str = None):
    start = date(year, month, 1).isoformat()
    last_day = monthrange(year, month)[1]
    end = date(year, month, last_day).isoformat()
    try:
        q = (
            supabase_admin.table("student_attendance")
            .select("*")
            .eq("school_id", school_id)
            .gte("date", start)
            .lte("date", end)
        )
        if class_id:
            q = q.eq("class_id", class_id)
        rows = q.execute().data or []
        return _enrich_attendance_rows(rows)
    except Exception:
        return []


def get_monthly_attendance_for_students(school_id: str, year: int, month: int, student_ids: list):
    if not student_ids:
        return []
    start = date(year, month, 1).isoformat()
    last_day = monthrange(year, month)[1]
    end = date(year, month, last_day).isoformat()
    try:
        rows = (
            supabase_admin.table("student_attendance")
            .select("*")
            .eq("school_id", school_id)
            .in_("student_id", student_ids)
            .gte("date", start)
            .lte("date", end)
            .execute()
            .data or []
        )
        return rows
    except Exception:
        return []


def build_monthly_attendance_summary(students: list, attendance_rows: list):
    summary = {}
    for student in students:
        summary[student["id"]] = {
            "student": student,
            "present": 0,
            "absent": 0,
            "late": 0,
            "leave": 0,
            "total": 0,
        }
    for row in attendance_rows:
        sid = row.get("student_id")
        if sid not in summary:
            continue
        summary[sid]["total"] += 1
        status = row.get("status")
        if status in ("present", "absent", "late", "leave"):
            summary[sid][status] += 1
    return sorted(summary.values(), key=lambda r: (r["student"].get("full_name") or "").lower())


def get_class_daily_summary(school_id: str, att_date: str, students: list):
    enrolled = len(students)
    if not students:
        return {"enrolled": 0, "total": 0, "present": 0, "absent": 0, "late": 0, "leave": 0, "unmarked": 0}

    student_ids = [s["id"] for s in students]
    try:
        rows = (
            supabase_admin.table("student_attendance")
            .select("status, student_id")
            .eq("school_id", school_id)
            .eq("date", att_date)
            .in_("student_id", student_ids)
            .execute()
            .data or []
        )
    except Exception:
        rows = []

    present = sum(1 for r in rows if r["status"] == "present")
    absent = sum(1 for r in rows if r["status"] == "absent")
    late = sum(1 for r in rows if r["status"] == "late")
    leave = sum(1 for r in rows if r["status"] == "leave")
    marked = len(rows)

    return {
        "enrolled": enrolled,
        "total": marked,
        "present": present,
        "absent": absent,
        "late": late,
        "leave": leave,
        "unmarked": max(enrolled - marked, 0),
    }


def get_absent_students(school_id: str, att_date: str):
    rows = get_daily_report(school_id, att_date)
    return [r for r in rows if r.get("status") == "absent"]


def get_late_students(school_id: str, att_date: str):
    rows = get_daily_report(school_id, att_date)
    return [r for r in rows if r.get("status") == "late"]


def get_student_history(student_id: str, school_id: str, limit=60):
    try:
        rows = (
            supabase_admin.table("student_attendance")
            .select("*")
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .order("date", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
        return rows
    except Exception:
        return []


def get_teacher_attendance_report(school_id: str, att_date: str = None, limit=30):
    try:
        q = (
            supabase_admin.table("teacher_attendance")
            .select("*")
            .eq("school_id", school_id)
            .order("date", desc=True)
            .limit(limit)
        )
        if att_date:
            q = q.eq("date", att_date)
        rows = q.execute().data or []
        teacher_ids = {r["teacher_id"] for r in rows}
        if not teacher_ids:
            return rows
        teachers = (
            supabase_admin.table("teachers")
            .select("id, full_name, employee_id")
            .in_("id", list(teacher_ids))
            .execute()
            .data or []
        )
        tmap = {t["id"]: t for t in teachers}
        for row in rows:
            row["teacher"] = tmap.get(row["teacher_id"])
        return rows
    except Exception:
        return []


def _enrich_attendance_rows(rows: list):
    if not rows:
        return []
    student_ids = {r["student_id"] for r in rows}
    students = (
        supabase_admin.table("students")
        .select("id, full_name, admission_number, roll_number, class_grade, section")
        .in_("id", list(student_ids))
        .execute()
        .data or []
    )
    smap = {s["id"]: s for s in students}
    enriched = []
    for row in rows:
        student = smap.get(row["student_id"], {})
        enriched.append({**row, "student": student, "student_name": student.get("full_name", "Unknown")})
    return enriched


def get_daily_summary(school_id: str, att_date: str):
    rows = get_daily_report(school_id, att_date)
    return {
        "total": len(rows),
        "present": sum(1 for r in rows if r["status"] == "present"),
        "absent": sum(1 for r in rows if r["status"] == "absent"),
        "late": sum(1 for r in rows if r["status"] == "late"),
        "leave": sum(1 for r in rows if r["status"] == "leave"),
    }


def notify_parents_of_absence(school_id: str, att_date: str, sent_by: str = None):
    absent = get_absent_students(school_id, att_date)
    if not absent:
        return 0, "No absent students for this date."

    notified = 0
    for record in absent:
        student_id = record["student_id"]
        student_name = record.get("student_name", "Your child")
        try:
            links = (
                supabase_admin.table("parent_student_links")
                .select("parent_id")
                .eq("student_id", student_id)
                .eq("school_id", school_id)
                .execute()
                .data or []
            )
            for link in links:
                from models.parent_model import send_notification
                result = send_notification(
                    link["parent_id"],
                    school_id,
                    f"Absence Notice — {att_date}",
                    f"{student_name} was marked absent on {att_date}. Please contact the school if this is incorrect.",
                    sent_by,
                )
                if result:
                    notified += 1
        except Exception:
            continue
    return notified, None


def export_csv_rows(school_id: str, att_date: str = None, year: int = None, month: int = None):
    if att_date:
        rows = get_daily_report(school_id, att_date)
    elif year and month:
        rows = get_monthly_report(school_id, year, month)
    else:
        rows = get_daily_report(school_id, date.today().isoformat())

    csv_lines = ["Date,Student,Admission No,Roll No,Class,Section,Status,Submitted"]
    for r in rows:
        s = r.get("student") or {}
        csv_lines.append(
            f"{r.get('date','')},{r.get('student_name','')},{s.get('admission_number','')},"
            f"{s.get('roll_number','')},{s.get('class_grade','')},{s.get('section','')},"
            f"{r.get('status','')},{'Yes' if r.get('is_submitted') else 'No'}"
        )
    return "\n".join(csv_lines)
