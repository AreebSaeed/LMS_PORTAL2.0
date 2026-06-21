from datetime import datetime, timezone
from models.supabase_client import supabase_admin

RELATIONS = ["father", "mother", "guardian"]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def search_parents(school_id: str, query=None):
    try:
        q = (
            supabase_admin.table("parents")
            .select("*")
            .eq("school_id", school_id)
            .order("full_name")
        )
        if query:
            term = query.strip()
            q = q.or_(
                f"full_name.ilike.%{term}%,"
                f"email.ilike.%{term}%,"
                f"phone.ilike.%{term}%,"
                f"cnic.ilike.%{term}%"
            )
        result = q.execute()
        return result.data or []
    except Exception:
        return []


def get_parent_by_id(parent_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("parents")
            .select("*")
            .eq("id", parent_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def get_linked_students(parent_id: str):
    try:
        links = (
            supabase_admin.table("parent_student_links")
            .select("student_id, relationship, linked_at")
            .eq("parent_id", parent_id)
            .execute()
            .data or []
        )
        if not links:
            return []
        student_ids = [l["student_id"] for l in links]
        students = (
            supabase_admin.table("students")
            .select("id, full_name, admission_number, roll_number, class_grade, section, status")
            .in_("id", student_ids)
            .execute()
            .data or []
        )
        student_map = {s["id"]: s for s in students}
        linked = []
        for link in links:
            student = student_map.get(link["student_id"])
            if student:
                linked.append({**student, "relationship": link.get("relationship"), "linked_at": link.get("linked_at")})
        return linked
    except Exception:
        return []


def get_notifications(parent_id: str, limit=10):
    try:
        result = (
            supabase_admin.table("parent_notifications")
            .select("*")
            .eq("parent_id", parent_id)
            .order("sent_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def _sync_student_links(parent_id: str, school_id: str, student_ids: list, relation: str):
    existing = (
        supabase_admin.table("parent_student_links")
        .select("student_id")
        .eq("parent_id", parent_id)
        .execute()
        .data or []
    )
    existing_ids = {r["student_id"] for r in existing}
    new_ids = set(student_ids)

    for sid in existing_ids - new_ids:
        supabase_admin.table("parent_student_links").delete().eq("parent_id", parent_id).eq("student_id", sid).execute()

    for sid in new_ids - existing_ids:
        supabase_admin.table("parent_student_links").insert({
            "parent_id": parent_id,
            "student_id": sid,
            "school_id": school_id,
            "relationship": relation,
        }).execute()


def create_parent(school_id: str, data: dict, student_ids: list = None):
    payload = {
        "school_id": school_id,
        "full_name": data["full_name"].strip(),
        "relation": data.get("relation") or "guardian",
        "cnic": (data.get("cnic") or "").strip() or None,
        "phone": (data.get("phone") or "").strip() or None,
        "whatsapp": (data.get("whatsapp") or "").strip() or None,
        "email": (data.get("email") or "").strip() or None,
        "address": (data.get("address") or "").strip() or None,
        "occupation": (data.get("occupation") or "").strip() or None,
        "is_active": data.get("is_active", True),
        "updated_at": _now_iso(),
    }
    result = supabase_admin.table("parents").insert(payload).execute()
    parent = result.data[0]

    if student_ids:
        _sync_student_links(parent["id"], school_id, student_ids, payload["relation"])

    return parent


def update_parent(parent_id: str, school_id: str, data: dict, student_ids: list = None):
    existing = get_parent_by_id(parent_id, school_id)
    if not existing:
        return None

    payload = {
        "full_name": data["full_name"].strip(),
        "relation": data.get("relation") or "guardian",
        "cnic": (data.get("cnic") or "").strip() or None,
        "phone": (data.get("phone") or "").strip() or None,
        "whatsapp": (data.get("whatsapp") or "").strip() or None,
        "email": (data.get("email") or "").strip() or None,
        "address": (data.get("address") or "").strip() or None,
        "occupation": (data.get("occupation") or "").strip() or None,
        "is_active": data.get("is_active", existing.get("is_active", True)),
        "updated_at": _now_iso(),
    }

    result = (
        supabase_admin.table("parents")
        .update(payload)
        .eq("id", parent_id)
        .eq("school_id", school_id)
        .execute()
    )
    parent = result.data[0] if result.data else None

    if parent and student_ids is not None:
        _sync_student_links(parent_id, school_id, student_ids, payload["relation"])

    return parent


def deactivate_parent(parent_id: str, school_id: str):
    result = (
        supabase_admin.table("parents")
        .update({"is_active": False, "updated_at": _now_iso()})
        .eq("id", parent_id)
        .eq("school_id", school_id)
        .execute()
    )
    return result.data[0] if result.data else None


def delete_parent(parent_id: str, school_id: str):
    result = (
        supabase_admin.table("parents")
        .delete()
        .eq("id", parent_id)
        .eq("school_id", school_id)
        .execute()
    )
    return bool(result.data)


def enable_parent_login(parent_id: str, school_id: str, email: str, password: str, full_name: str):
    parent = get_parent_by_id(parent_id, school_id)
    if not parent:
        return None, "Parent not found."

    if parent.get("user_id"):
        return None, "Login already enabled for this parent."

    if not email:
        return None, "Email is required for login access."

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
            "role": "parent",
            "school_id": school_id,
            "phone": parent.get("phone"),
            "is_active": True,
        }).execute()

        result = (
            supabase_admin.table("parents")
            .update({
                "user_id": user_id,
                "email": email,
                "login_enabled": True,
                "updated_at": _now_iso(),
            })
            .eq("id", parent_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as e:
        err = str(e)
        if "already been registered" in err or "already exists" in err.lower():
            return None, "This email is already registered. Use a different email."
        return None, "Could not create login. Check email and try again."


def reset_parent_password(parent_id: str, school_id: str, new_password: str):
    parent = get_parent_by_id(parent_id, school_id)
    if not parent or not parent.get("user_id"):
        return False, "No login account linked to this parent."

    try:
        supabase_admin.auth.admin.update_user_by_id(
            parent["user_id"],
            {"password": new_password},
        )
        return True, None
    except Exception:
        return False, "Password reset failed."


def send_notification(parent_id: str, school_id: str, subject: str, message: str, sent_by: str = None):
    payload = {
        "parent_id": parent_id,
        "school_id": school_id,
        "subject": subject.strip(),
        "message": message.strip(),
        "sent_by": sent_by,
    }
    try:
        result = supabase_admin.table("parent_notifications").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_linked_student_ids(parent_id: str):
    try:
        rows = (
            supabase_admin.table("parent_student_links")
            .select("student_id")
            .eq("parent_id", parent_id)
            .execute()
            .data or []
        )
        return [r["student_id"] for r in rows]
    except Exception:
        return []


def get_parent_by_user_id(user_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("parents")
            .select("*")
            .eq("user_id", user_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def parent_has_student(parent_id: str, student_id: str) -> bool:
    return student_id in get_linked_student_ids(parent_id)
