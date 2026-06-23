from datetime import datetime, timezone
from typing import Optional

from models.supabase_client import supabase_admin
from models.class_model import get_class_teachers

RECIPIENT_ADMIN = "admin"
RECIPIENT_TEACHER = "teacher"


def get_teachers_for_student(student: dict, school_id: str) -> list:
    class_id = student.get("class_id")
    if not class_id:
        return []
    return get_class_teachers(class_id, school_id)


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


def _get_teacher_user_id(teacher_id: str, school_id: str):
    try:
        row = (
            supabase_admin.table("teachers")
            .select("user_id")
            .eq("id", teacher_id)
            .eq("school_id", school_id)
            .limit(1)
            .execute()
            .data
        )
        return row[0].get("user_id") if row else None
    except Exception:
        return None


def _create_staff_notification(
    user_id: str, school_id: str, subject: str, message: str, reference_id: str
):
    try:
        supabase_admin.table("staff_notifications").insert({
            "user_id": user_id,
            "school_id": school_id,
            "subject": subject,
            "message": message[:500],
            "category": "student_message",
            "reference_id": reference_id,
        }).execute()
    except Exception:
        pass


def _notify_student_reply(student_id: str, school_id: str, subject: str, reply: str, sent_by: str):
    try:
        supabase_admin.table("student_notifications").insert({
            "student_id": student_id,
            "school_id": school_id,
            "subject": subject,
            "message": reply[:500],
            "sent_by": sent_by,
        }).execute()
    except Exception:
        pass


def get_student_messages(student_id: str, school_id: str, limit=30):
    try:
        return (
            supabase_admin.table("student_messages")
            .select("*, teachers(full_name)")
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
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


def send_student_message(
    student_id: str,
    school_id: str,
    subject: str,
    message: str,
    recipient_type: str = RECIPIENT_ADMIN,
    teacher_id: Optional[str] = None,
):
    subject = subject.strip()
    message = message.strip()
    if not subject or not message:
        return None

    payload = {
        "student_id": student_id,
        "school_id": school_id,
        "subject": subject,
        "message": message,
        "status": "open",
        "recipient_type": recipient_type,
    }
    if recipient_type == RECIPIENT_TEACHER:
        if not teacher_id:
            return None
        payload["teacher_id"] = teacher_id

    try:
        result = supabase_admin.table("student_messages").insert(payload).execute()
        row = result.data[0] if result.data else None
        if not row:
            return None

        msg_id = row["id"]
        notif_subject = f"New student message: {subject}"
        preview = message[:200] + ("…" if len(message) > 200 else "")

        if recipient_type == RECIPIENT_ADMIN:
            for uid in _get_admin_user_ids(school_id):
                _create_staff_notification(uid, school_id, notif_subject, preview, msg_id)
        elif teacher_id:
            uid = _get_teacher_user_id(teacher_id, school_id)
            if uid:
                _create_staff_notification(uid, school_id, notif_subject, preview, msg_id)
        return row
    except Exception:
        return None


def get_messages_for_admin(school_id: str, limit=50):
    try:
        return (
            supabase_admin.table("student_messages")
            .select("*, students(full_name, admission_number, roll_number)")
            .eq("school_id", school_id)
            .eq("recipient_type", RECIPIENT_ADMIN)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        try:
            return (
                supabase_admin.table("student_messages")
                .select("*, students(full_name, admission_number, roll_number)")
                .eq("school_id", school_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data or []
            )
        except Exception:
            return []


def get_messages_for_teacher(teacher_id: str, school_id: str, limit=50):
    try:
        return (
            supabase_admin.table("student_messages")
            .select("*, students(full_name, admission_number, roll_number)")
            .eq("school_id", school_id)
            .eq("teacher_id", teacher_id)
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
            supabase_admin.table("student_messages")
            .select("*, students(full_name)")
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
            supabase_admin.table("student_messages")
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
        student = msg.get("students") or {}
        student_name = student.get("full_name", "Student")
        _notify_student_reply(
            msg["student_id"],
            school_id,
            f"Reply to: {msg.get('subject', 'your message')}",
            f"{student_name}, you received a reply to your message:\n\n{reply_text}",
            user_id,
        )
        return True
    except Exception:
        return False


def count_unread_student_message_notifications(user_id: str, school_id: str) -> int:
    try:
        result = (
            supabase_admin.table("staff_notifications")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("school_id", school_id)
            .eq("category", "student_message")
            .eq("is_read", False)
            .execute()
        )
        return result.count or 0
    except Exception:
        return 0


def get_staff_message_notifications(user_id: str, school_id: str, limit=10):
    try:
        return (
            supabase_admin.table("staff_notifications")
            .select("*")
            .eq("user_id", user_id)
            .eq("school_id", school_id)
            .eq("category", "student_message")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []


def mark_student_message_notifications_read(user_id: str, school_id: str):
    try:
        supabase_admin.table("staff_notifications").update({
            "is_read": True,
        }).eq("user_id", user_id).eq("school_id", school_id).eq(
            "category", "student_message"
        ).eq("is_read", False).execute()
    except Exception:
        pass


def recipient_label(message: dict) -> str:
    if message.get("recipient_type") == RECIPIENT_TEACHER:
        teachers = message.get("teachers")
        if isinstance(teachers, dict) and teachers.get("full_name"):
            return f"Teacher: {teachers['full_name']}"
        return "Teacher"
    return "School Admin"
