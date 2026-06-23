from datetime import datetime, timezone
from typing import Optional

from models.supabase_client import supabase_admin
from models.parent_model import send_notification as notify_parent


def _get_admin_user_ids(school_id: str) -> list:
    try:
        rows = (
            supabase_admin.table("user_profiles")
            .select("id")
            .eq("school_id", school_id)
            .eq("role", "school_admin")
            .execute()
            .data or []
        )
        return [r["id"] for r in rows if r.get("id")]
    except Exception:
        return []


def _create_staff_notification(
    user_id: str, school_id: str, subject: str, message: str, reference_id: str
):
    try:
        supabase_admin.table("staff_notifications").insert({
            "user_id": user_id,
            "school_id": school_id,
            "subject": subject,
            "message": message[:500],
            "category": "parent_message",
            "reference_id": reference_id,
        }).execute()
    except Exception:
        pass


def student_reference(student: Optional[dict]) -> str:
    if not student:
        return "General inquiry"
    name = student.get("full_name", "Student")
    parts = [name]
    if student.get("roll_number"):
        parts.append(f"Roll: {student['roll_number']}")
    reg = student.get("admission_number") or student.get("registration_number")
    if reg:
        parts.append(f"Reg: {reg}")
    return " · ".join(parts)


def _fetch_student(student_id: str, school_id: str):
    if not student_id:
        return None
    try:
        rows = (
            supabase_admin.table("students")
            .select("id, full_name, admission_number, roll_number")
            .eq("id", student_id)
            .eq("school_id", school_id)
            .limit(1)
            .execute()
            .data or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _fetch_parent_name(parent_id: str, school_id: str) -> str:
    try:
        rows = (
            supabase_admin.table("parents")
            .select("full_name")
            .eq("id", parent_id)
            .eq("school_id", school_id)
            .limit(1)
            .execute()
            .data or []
        )
        return rows[0].get("full_name", "Parent") if rows else "Parent"
    except Exception:
        return "Parent"


def get_parent_messages(parent_id: str, school_id: str, limit=30):
    try:
        return (
            supabase_admin.table("parent_messages")
            .select("*, students(full_name, admission_number, roll_number)")
            .eq("parent_id", parent_id)
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
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


def send_parent_message(
    parent_id: str,
    school_id: str,
    subject: str,
    message: str,
    student_id: Optional[str] = None,
):
    subject = subject.strip()
    message = message.strip()
    if not subject or not message:
        return None

    payload = {
        "parent_id": parent_id,
        "school_id": school_id,
        "subject": subject,
        "message": message,
        "student_id": student_id,
        "status": "open",
    }
    try:
        result = supabase_admin.table("parent_messages").insert(payload).execute()
        row = result.data[0] if result.data else None
        if not row:
            return None

        msg_id = row["id"]
        parent_name = _fetch_parent_name(parent_id, school_id)
        student = _fetch_student(student_id, school_id) if student_id else None
        child_line = student_reference(student)
        preview = (
            f"From {parent_name} (re: {child_line})\n\n{message[:180]}"
            + ("…" if len(message) > 180 else "")
        )
        notif_subject = f"New parent message: {subject}"

        for uid in _get_admin_user_ids(school_id):
            _create_staff_notification(uid, school_id, notif_subject, preview, msg_id)
        return row
    except Exception:
        return None


def get_messages_for_admin(school_id: str, limit=50):
    try:
        return (
            supabase_admin.table("parent_messages")
            .select("*, parents(full_name, phone), students(full_name, admission_number, roll_number)")
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []


def get_message_by_id(message_id: str, school_id: str):
    try:
        rows = (
            supabase_admin.table("parent_messages")
            .select("*, parents(full_name, phone), students(full_name, admission_number, roll_number)")
            .eq("id", message_id)
            .eq("school_id", school_id)
            .limit(1)
            .execute()
            .data or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def reply_to_message(message_id: str, school_id: str, reply_text: str, user_id: str):
    reply_text = reply_text.strip()
    if not reply_text:
        return False

    try:
        result = (
            supabase_admin.table("parent_messages")
            .update({
                "admin_reply": reply_text,
                "status": "replied",
                "replied_at": datetime.now(timezone.utc).isoformat(),
                "replied_by": user_id,
            })
            .eq("id", message_id)
            .eq("school_id", school_id)
            .execute()
        )
        if not result.data:
            return False

        msg = result.data[0]
        parent_name = (msg.get("parents") or {}).get("full_name", "Parent")
        notify_parent(
            msg["parent_id"],
            school_id,
            f"Reply to: {msg.get('subject', 'your message')}",
            f"Dear {parent_name},\n\nYou received a reply from the school:\n\n{reply_text}",
            user_id,
        )
        return True
    except Exception:
        return False


def count_unread_parent_message_notifications(user_id: str, school_id: str) -> int:
    try:
        result = (
            supabase_admin.table("staff_notifications")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("school_id", school_id)
            .eq("category", "parent_message")
            .eq("is_read", False)
            .execute()
        )
        return result.count or 0
    except Exception:
        return 0


def get_staff_parent_notifications(user_id: str, school_id: str, limit=10):
    try:
        return (
            supabase_admin.table("staff_notifications")
            .select("*")
            .eq("user_id", user_id)
            .eq("school_id", school_id)
            .eq("category", "parent_message")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []


def mark_parent_message_notifications_read(user_id: str, school_id: str):
    try:
        supabase_admin.table("staff_notifications").update({
            "is_read": True,
        }).eq("user_id", user_id).eq("school_id", school_id).eq(
            "category", "parent_message"
        ).eq("is_read", False).execute()
    except Exception:
        pass


def parent_child_label(message: dict) -> str:
    students = message.get("students")
    if isinstance(students, dict):
        return student_reference(students)
    return "General inquiry"
