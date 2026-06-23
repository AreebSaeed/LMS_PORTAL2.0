from datetime import date, datetime, timezone
from calendar import monthrange
from models.supabase_client import supabase_admin
from models.parent_model import get_linked_students, get_notifications


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _fee_lookup_ids(students: list) -> list:
    ids = []
    for s in students:
        ids.append(s["id"])
        if s.get("user_id"):
            ids.append(s["user_id"])
    return list(set(ids))


def _match_student_for_fee(students: list, fee_student_id: str):
    for s in students:
        if s["id"] == fee_student_id or s.get("user_id") == fee_student_id:
            return s
    return None


def get_dashboard_data(parent_id: str, school_id: str, student_id: str = None):
    children = get_linked_students(parent_id)
    selected = None
    if student_id:
        selected = next((c for c in children if c["id"] == student_id), None)
    if not selected and children:
        selected = children[0]

    attendance_summary = get_attendance_summary(selected["id"], school_id) if selected else {}
    pending_fees = get_pending_fees_total(children, school_id)
    latest_homework = get_homework_for_students(children, school_id, limit=5)
    latest_result = get_latest_result(children, school_id)
    announcements = get_announcements(school_id, limit=5, role="parent")
    upcoming_exams = get_upcoming_exams(children, school_id, limit=5)
    notifications = get_notifications(parent_id, limit=5)

    return {
        "children": children,
        "children_count": len(children),
        "selected_student": selected,
        "attendance_summary": attendance_summary,
        "pending_fees": pending_fees,
        "latest_homework": latest_homework,
        "latest_result": latest_result,
        "announcements": announcements,
        "upcoming_exams": upcoming_exams,
        "notifications": notifications,
    }


def get_attendance_summary(student_id: str, school_id: str, year: int = None, month: int = None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    start = date(year, month, 1).isoformat()
    last_day = monthrange(year, month)[1]
    end = date(year, month, last_day).isoformat()

    try:
        rows = (
            supabase_admin.table("student_attendance")
            .select("status")
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .gte("date", start)
            .lte("date", end)
            .execute()
            .data or []
        )
    except Exception:
        rows = []

    total = len(rows)
    present = sum(1 for r in rows if r["status"] == "present")
    absent = sum(1 for r in rows if r["status"] == "absent")
    late = sum(1 for r in rows if r["status"] == "late")
    leave = sum(1 for r in rows if r["status"] == "leave")
    attended = present + late
    pct = round((attended / total) * 100) if total else 0

    return {
        "total": total,
        "present": present,
        "absent": absent,
        "late": late,
        "leave": leave,
        "attendance_pct": pct,
        "year": year,
        "month": month,
    }


def get_daily_attendance(student_id: str, school_id: str, att_date: str):
    try:
        rows = (
            supabase_admin.table("student_attendance")
            .select("*")
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .eq("date", att_date)
            .limit(1)
            .execute()
            .data or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def get_monthly_attendance(student_id: str, school_id: str, year: int, month: int):
    start = date(year, month, 1).isoformat()
    last_day = monthrange(year, month)[1]
    end = date(year, month, last_day).isoformat()
    try:
        return (
            supabase_admin.table("student_attendance")
            .select("*")
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .gte("date", start)
            .lte("date", end)
            .order("date")
            .execute()
            .data or []
        )
    except Exception:
        return []


def get_fees_for_students(students: list, school_id: str):
    if not students:
        return []
    lookup_ids = _fee_lookup_ids(students)
    try:
        rows = (
            supabase_admin.table("fee_records")
            .select("*")
            .eq("school_id", school_id)
            .in_("student_id", lookup_ids)
            .order("due_date", desc=True)
            .execute()
            .data or []
        )
    except Exception:
        return []

    from models.fee_model import enrich_fee_record, _load_students_map, _load_classes_map
    class_ids = {r["class_id"] for r in rows if r.get("class_id")}
    smap = _load_students_map(lookup_ids, school_id)
    cmap = _load_classes_map(class_ids, school_id)

    enriched = []
    for row in rows:
        if row.get("is_void"):
            continue
        fee = enrich_fee_record(row, smap, cmap)
        student = _match_student_for_fee(students, row["student_id"])
        if student:
            fee["student"] = student
            fee["student_name"] = student["full_name"]
        enriched.append(fee)
    return enriched


def get_pending_fees_total(students: list, school_id: str) -> float:
    fees = get_fees_for_students(students, school_id)
    return sum(
        f["balance"] for f in fees
        if f.get("status") in ("pending", "partial", "overdue")
    )


def get_fee_by_id(fee_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("fee_records")
            .select("*")
            .eq("id", fee_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def get_receipt_for_fee(fee_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("fee_receipts")
            .select("*")
            .eq("fee_record_id", fee_id)
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def ensure_receipt(fee: dict, student: dict, school_id: str):
    existing = get_receipt_for_fee(fee["id"], school_id)
    if existing:
        return existing

    if fee.get("status") != "paid" and float(fee.get("amount_paid") or 0) <= 0:
        return None

    receipt_number = f"RCP-{fee['id'][:8].upper()}-{date.today().strftime('%Y%m%d')}"
    payload = {
        "school_id": school_id,
        "fee_record_id": fee["id"],
        "receipt_number": receipt_number,
        "student_id": student["id"] if student else None,
        "amount_paid": float(fee.get("amount_paid") or fee.get("amount") or 0),
        "payment_date": fee.get("paid_at") or _now_iso(),
        "payment_method": "cash",
    }
    try:
        result = supabase_admin.table("fee_receipts").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        return get_receipt_for_fee(fee["id"], school_id)


def get_homework_for_students(students: list, school_id: str, limit=20):
    from models.homework_model import get_homework_for_students as _get
    return _get(students, school_id, limit)


def get_exam_results_for_students(students: list, school_id: str, limit=30):
    if not students:
        return []
    all_results = []
    for s in students:
        from models.student_portal_model import get_exam_results
        for r in get_exam_results(s["id"], school_id, limit=limit):
            all_results.append({**r, "student_name": s["full_name"], "student_id": s["id"]})
    all_results.sort(key=lambda r: str(r.get("published_at") or r.get("exam", {}).get("created_at") or ""), reverse=True)
    return all_results[:limit]


def get_latest_result(students: list, school_id: str):
    results = get_exam_results_for_students(students, school_id, limit=1)
    return results[0] if results else None


def get_upcoming_exams(students: list, school_id: str, limit=5):
    if not students:
        return []
    class_ids = {s["class_id"] for s in students if s.get("class_id")}
    today = date.today().isoformat()
    try:
        rows = (
            supabase_admin.table("exams")
            .select("*")
            .eq("school_id", school_id)
            .gte("exam_date", today)
            .order("exam_date")
            .limit(limit * 2)
            .execute()
            .data or []
        )
    except Exception:
        return []

    if class_ids:
        rows = [r for r in rows if not r.get("class_id") or r["class_id"] in class_ids]
    return rows[:limit]


def get_class_timetable(class_id: str, school_id: str):
    if not class_id:
        return []
    try:
        rows = (
            supabase_admin.table("teacher_timetable")
            .select("*")
            .eq("school_id", school_id)
            .eq("class_id", class_id)
            .order("day_of_week")
            .execute()
            .data or []
        )
    except Exception:
        return []

    subject_ids = {r["subject_id"] for r in rows if r.get("subject_id")}
    teacher_ids = {r["teacher_id"] for r in rows if r.get("teacher_id")}
    subject_map = {}
    teacher_map = {}
    if subject_ids:
        subjects = supabase_admin.table("subjects").select("id, name").in_("id", list(subject_ids)).execute().data or []
        subject_map = {s["id"]: s["name"] for s in subjects}
    if teacher_ids:
        teachers = supabase_admin.table("teachers").select("id, full_name").in_("id", list(teacher_ids)).execute().data or []
        teacher_map = {t["id"]: t["full_name"] for t in teachers}

    day_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    for row in rows:
        row["subject_name"] = subject_map.get(row.get("subject_id"), "—")
        row["teacher_name"] = teacher_map.get(row.get("teacher_id"), "—")

    rows.sort(key=lambda r: (day_order.index(r["day_of_week"]) if r["day_of_week"] in day_order else 99, r.get("start_time") or ""))
    return rows


def get_announcements(school_id: str, limit=20, role=None):
    from models.announcement_model import list_announcements
    return list_announcements(school_id, limit=limit, role=role)


def get_parent_messages(parent_id: str, school_id: str, limit=30):
    try:
        return (
            supabase_admin.table("parent_messages")
            .select("*")
            .eq("parent_id", parent_id)
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []


def send_parent_message(parent_id: str, school_id: str, subject: str, message: str, student_id: str = None):
    payload = {
        "parent_id": parent_id,
        "school_id": school_id,
        "subject": subject.strip(),
        "message": message.strip(),
        "student_id": student_id,
        "status": "open",
    }
    try:
        result = supabase_admin.table("parent_messages").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None
