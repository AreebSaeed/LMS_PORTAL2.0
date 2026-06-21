from datetime import date
from models.supabase_client import supabase_admin
from models.school_model import get_school_stats


def _table_count(table: str, school_id: str, filters=None) -> int:
    """Count rows in a table for a school, returning 0 if the table is missing."""
    try:
        query = (
            supabase_admin.table(table)
            .select("id", count="exact")
            .eq("school_id", school_id)
        )
        if filters:
            for key, value in filters.items():
                if key.endswith("__gte"):
                    query = query.gte(key.replace("__gte", ""), value)
                elif key.endswith("__lte"):
                    query = query.lte(key.replace("__lte", ""), value)
                else:
                    query = query.eq(key, value)
        result = query.execute()
        return result.count or 0
    except Exception:
        return 0


def _fetch_rows(table: str, school_id: str, select="*", order_by=None, limit=10, filters=None):
    """Fetch rows from a table, returning [] if the table is missing."""
    try:
        query = supabase_admin.table(table).select(select).eq("school_id", school_id)
        if filters:
            for key, value in filters.items():
                if key.endswith("__gte"):
                    query = query.gte(key.replace("__gte", ""), value)
                elif key.endswith("__lte"):
                    query = query.lte(key.replace("__lte", ""), value)
                else:
                    query = query.eq(key, value)
        if order_by:
            desc = order_by.startswith("-")
            col = order_by.lstrip("-")
            query = query.order(col, desc=desc)
        query = query.limit(limit)
        result = query.execute()
        return result.data or []
    except Exception:
        return []


def _sum_fee_paid_this_month(school_id: str) -> float:
    try:
        month_start = date.today().replace(day=1).isoformat()
        rows = (
            supabase_admin.table("fee_records")
            .select("amount_paid, paid_at")
            .eq("school_id", school_id)
            .gte("paid_at", f"{month_start}T00:00:00")
            .execute()
            .data or []
        )
        return sum(float(r.get("amount_paid") or 0) for r in rows)
    except Exception:
        return 0.0


def _sum_pending_fees(school_id: str) -> float:
    try:
        rows = (
            supabase_admin.table("fee_records")
            .select("amount, amount_paid, status")
            .eq("school_id", school_id)
            .in_("status", ["pending", "partial", "overdue"])
            .execute()
            .data or []
        )
        total = 0.0
        for row in rows:
            amount = float(row.get("amount") or 0)
            paid = float(row.get("amount_paid") or 0)
            total += max(amount - paid, 0)
        return total
    except Exception:
        return 0.0


def _attendance_today(school_id: str, today: str):
    try:
        rows = (
            supabase_admin.table("student_attendance")
            .select("status, student_id")
            .eq("school_id", school_id)
            .eq("date", today)
            .execute()
            .data or []
        )
        if not rows:
            rows = (
                supabase_admin.table("attendance_records")
                .select("status, student_id")
                .eq("school_id", school_id)
                .eq("date", today)
                .execute()
                .data or []
            )
        present = sum(1 for r in rows if r["status"] in ("present", "late"))
        absent = sum(1 for r in rows if r["status"] == "absent")
        absent_ids = [r["student_id"] for r in rows if r["status"] == "absent"]
        return present, absent, absent_ids
    except Exception:
        return 0, 0, []


def _student_names(student_ids: list) -> list:
    if not student_ids:
        return []
    try:
        rows = (
            supabase_admin.table("students")
            .select("id, full_name")
            .in_("id", student_ids)
            .execute()
            .data or []
        )
        if rows:
            name_map = {r["id"]: r["full_name"] for r in rows}
            return [{"id": sid, "full_name": name_map.get(sid, "Unknown")} for sid in student_ids]
        rows = (
            supabase_admin.table("user_profiles")
            .select("id, full_name")
            .in_("id", student_ids)
            .execute()
            .data or []
        )
        name_map = {r["id"]: r["full_name"] for r in rows}
        return [{"id": sid, "full_name": name_map.get(sid, "Unknown")} for sid in student_ids]
    except Exception:
        return []


def _new_admissions_count(school_id: str) -> int:
    try:
        month_start = date.today().replace(day=1).isoformat()
        rows = (
            supabase_admin.table("admissions")
            .select("id")
            .eq("school_id", school_id)
            .gte("created_at", f"{month_start}T00:00:00")
            .execute()
            .data or []
        )
        return len(rows)
    except Exception:
        return 0


def get_admin_dashboard_data(school_id: str) -> dict:
    """Aggregate all metrics and lists for the school Admin Dashboard."""
    today = date.today().isoformat()
    user_stats = get_school_stats(school_id)
    try:
        supabase_admin.table("students").select("id").limit(1).execute()
        user_stats["students_count"] = _table_count("students", school_id)
    except Exception:
        pass
    try:
        supabase_admin.table("parents").select("id").limit(1).execute()
        user_stats["parents_count"] = _table_count("parents", school_id)
    except Exception:
        pass
    try:
        supabase_admin.table("teachers").select("id").limit(1).execute()
        user_stats["teachers_count"] = _table_count("teachers", school_id)
    except Exception:
        pass

    present_today, absent_today, absent_ids = _attendance_today(school_id, today)
    absent_students = _student_names(absent_ids[:10])

    upcoming_exams = _fetch_rows(
        "exams",
        school_id,
        select="id, title, exam_date",
        order_by="exam_date",
        limit=5,
        filters={"exam_date__gte": today},
    )

    recent_announcements = _fetch_rows(
        "announcements",
        school_id,
        select="id, title, body, created_at",
        order_by="-created_at",
        limit=5,
    )

    monthly_fee = _sum_fee_paid_this_month(school_id)
    pending_fees = _sum_pending_fees(school_id)

    marked_today = present_today + absent_today
    attendance_rate = (
        round(present_today / marked_today * 100) if marked_today else 0
    )

    return {
        **user_stats,
        "classes_count": _table_count("classes", school_id),
        "present_today": present_today,
        "absent_today": absent_today,
        "attendance_rate": attendance_rate,
        "monthly_fee_collection": monthly_fee,
        "pending_fees": pending_fees,
        "upcoming_exams_count": _table_count(
            "exams", school_id, {"exam_date__gte": today}
        ),
        "new_admissions": _new_admissions_count(school_id),
        "absent_students": absent_students,
        "upcoming_exams": upcoming_exams,
        "recent_announcements": recent_announcements,
        "today": today,
    }
