import uuid
from datetime import datetime, timezone
from models.supabase_client import supabase_admin

STORAGE_BUCKET = "student-documents"

STUDENT_STATUSES = ["active", "inactive", "transferred", "graduated", "left"]
GENDERS = ["male", "female", "other"]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_classes_for_school(school_id: str):
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


def search_students(school_id: str, query=None, class_grade=None, section=None, status=None):
    try:
        q = (
            supabase_admin.table("students")
            .select("*")
            .eq("school_id", school_id)
            .order("full_name")
        )
        if query:
            term = query.strip()
            q = q.or_(
                f"full_name.ilike.%{term}%,"
                f"admission_number.ilike.%{term}%,"
                f"roll_number.ilike.%{term}%"
            )
        if class_grade:
            q = q.eq("class_grade", class_grade)
        if section:
            q = q.eq("section", section)
        if status:
            q = q.eq("status", status)
        result = q.execute()
        return result.data or []
    except Exception:
        return []


def get_student_by_id(student_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("students")
            .select("*")
            .eq("id", student_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def get_student_by_user_id(user_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("students")
            .select("*")
            .eq("user_id", user_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def get_student_documents(student_id: str):
    try:
        result = (
            supabase_admin.table("student_documents")
            .select("*")
            .eq("student_id", student_id)
            .order("uploaded_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def get_academic_history(student_id: str):
    try:
        result = (
            supabase_admin.table("student_academic_history")
            .select("*")
            .eq("student_id", student_id)
            .order("recorded_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def _class_fields(class_id: str, school_id: str):
    if not class_id:
        return None, None, None
    try:
        row = (
            supabase_admin.table("classes")
            .select("id, name, grade, section")
            .eq("id", class_id)
            .eq("school_id", school_id)
            .single()
            .execute()
            .data
        )
        if row:
            return row["id"], row.get("grade") or row.get("name"), row.get("section")
    except Exception:
        pass
    return class_id, None, None


def create_student(school_id: str, data: dict):
    class_id = data.get("class_id") or None
    cid, grade, section = _class_fields(class_id, school_id)

    payload = {
        "school_id": school_id,
        "full_name": data["full_name"].strip(),
        "admission_number": data["admission_number"].strip(),
        "roll_number": (data.get("roll_number") or "").strip() or None,
        "date_of_birth": data.get("date_of_birth") or None,
        "gender": data.get("gender") or None,
        "class_id": cid,
        "class_grade": data.get("class_grade") or grade,
        "section": data.get("section") or section,
        "batch_session": (data.get("batch_session") or "").strip() or None,
        "address": (data.get("address") or "").strip() or None,
        "contact_number": (data.get("contact_number") or "").strip() or None,
        "parent_name": (data.get("parent_name") or "").strip() or None,
        "parent_cnic": (data.get("parent_cnic") or "").strip() or None,
        "emergency_contact": (data.get("emergency_contact") or "").strip() or None,
        "previous_school": (data.get("previous_school") or "").strip() or None,
        "status": data.get("status") or "active",
        "updated_at": _now_iso(),
    }

    result = supabase_admin.table("students").insert(payload).execute()
    student = result.data[0]

    if payload.get("class_grade") or payload.get("section"):
        add_academic_history(
            student["id"],
            school_id,
            {
                "academic_year": payload.get("batch_session") or datetime.now().strftime("%Y"),
                "class_grade": payload.get("class_grade"),
                "section": payload.get("section"),
                "notes": "Initial enrollment",
            },
        )

    return student


def update_student(student_id: str, school_id: str, data: dict):
    existing = get_student_by_id(student_id, school_id)
    if not existing:
        return None

    class_id = data.get("class_id") or None
    cid, grade, section = _class_fields(class_id, school_id)

    payload = {
        "full_name": data["full_name"].strip(),
        "admission_number": data["admission_number"].strip(),
        "roll_number": (data.get("roll_number") or "").strip() or None,
        "date_of_birth": data.get("date_of_birth") or None,
        "gender": data.get("gender") or None,
        "class_id": cid,
        "class_grade": data.get("class_grade") or grade,
        "section": data.get("section") or section,
        "batch_session": (data.get("batch_session") or "").strip() or None,
        "address": (data.get("address") or "").strip() or None,
        "contact_number": (data.get("contact_number") or "").strip() or None,
        "parent_name": (data.get("parent_name") or "").strip() or None,
        "parent_cnic": (data.get("parent_cnic") or "").strip() or None,
        "emergency_contact": (data.get("emergency_contact") or "").strip() or None,
        "previous_school": (data.get("previous_school") or "").strip() or None,
        "status": data.get("status") or existing.get("status", "active"),
        "updated_at": _now_iso(),
    }

    if (
        payload.get("class_grade") != existing.get("class_grade")
        or payload.get("section") != existing.get("section")
    ):
        add_academic_history(
            student_id,
            school_id,
            {
                "academic_year": payload.get("batch_session") or datetime.now().strftime("%Y"),
                "class_grade": payload.get("class_grade"),
                "section": payload.get("section"),
                "notes": "Class assignment updated",
            },
        )

    result = (
        supabase_admin.table("students")
        .update(payload)
        .eq("id", student_id)
        .eq("school_id", school_id)
        .execute()
    )
    return result.data[0] if result.data else None


def update_student_status(student_id: str, school_id: str, status: str):
    if status not in STUDENT_STATUSES:
        return None
    result = (
        supabase_admin.table("students")
        .update({"status": status, "updated_at": _now_iso()})
        .eq("id", student_id)
        .eq("school_id", school_id)
        .execute()
    )
    return result.data[0] if result.data else None


def update_student_class_assignment(student_id: str, school_id: str, class_id: str = None):
    student = get_student_by_id(student_id, school_id)
    if not student:
        return None

    cid, grade, section = _class_fields(class_id, school_id) if class_id else (None, None, None)
    payload = {
        "class_id": cid,
        "class_grade": grade,
        "section": section,
        "updated_at": _now_iso(),
    }
    result = (
        supabase_admin.table("students")
        .update(payload)
        .eq("id", student_id)
        .eq("school_id", school_id)
        .execute()
    )
    updated = result.data[0] if result.data else None

    if updated:
        add_academic_history(
            student_id,
            school_id,
            {
                "academic_year": updated.get("batch_session") or datetime.now().strftime("%Y"),
                "class_grade": updated.get("class_grade"),
                "section": updated.get("section"),
                "notes": "Class assignment updated from student settings",
            },
        )
    return updated


def delete_student(student_id: str, school_id: str):
    result = (
        supabase_admin.table("students")
        .delete()
        .eq("id", student_id)
        .eq("school_id", school_id)
        .execute()
    )
    return bool(result.data)


def add_academic_history(student_id: str, school_id: str, data: dict):
    payload = {
        "student_id": student_id,
        "school_id": school_id,
        "academic_year": data["academic_year"],
        "class_grade": data.get("class_grade"),
        "section": data.get("section"),
        "result_summary": data.get("result_summary"),
        "notes": data.get("notes"),
    }
    result = supabase_admin.table("student_academic_history").insert(payload).execute()
    return result.data[0] if result.data else None


def upload_file(school_id: str, student_id: str, file_bytes: bytes, filename: str, content_type: str):
    safe_name = filename.replace(" ", "_")
    path = f"{school_id}/{student_id}/{uuid.uuid4().hex}_{safe_name}"
    try:
        supabase_admin.storage.from_(STORAGE_BUCKET).upload(
            path,
            file_bytes,
            {"content-type": content_type or "application/octet-stream", "upsert": "true"},
        )
        public = supabase_admin.storage.from_(STORAGE_BUCKET).get_public_url(path)
        return public
    except Exception:
        return None


def update_student_photo(student_id: str, school_id: str, photo_url: str):
    result = (
        supabase_admin.table("students")
        .update({"photo_url": photo_url, "updated_at": _now_iso()})
        .eq("id", student_id)
        .eq("school_id", school_id)
        .execute()
    )
    return result.data[0] if result.data else None


def add_document(student_id: str, school_id: str, file_name: str, file_url: str, doc_type: str = "general"):
    payload = {
        "student_id": student_id,
        "school_id": school_id,
        "file_name": file_name,
        "file_url": file_url,
        "doc_type": doc_type,
    }
    result = supabase_admin.table("student_documents").insert(payload).execute()
    return result.data[0] if result.data else None


def get_distinct_class_sections(school_id: str):
    students = search_students(school_id)
    grades = sorted({s["class_grade"] for s in students if s.get("class_grade")})
    sections = sorted({s["section"] for s in students if s.get("section")})
    return grades, sections


def enable_student_login(student_id: str, school_id: str, email: str, password: str, full_name: str):
    student = get_student_by_id(student_id, school_id)
    if not student:
        return None, "Student not found."
    if student.get("user_id"):
        return None, "Login already enabled for this student."
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
            "role": "student",
            "school_id": school_id,
            "phone": student.get("contact_number"),
            "is_active": True,
        }).execute()

        result = (
            supabase_admin.table("students")
            .update({
                "user_id": user_id,
                "email": email,
                "login_enabled": True,
                "updated_at": _now_iso(),
            })
            .eq("id", student_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception as e:
        err = str(e)
        if "already been registered" in err or "already exists" in err.lower():
            return None, "This email is already registered. Use a different email."
        return None, "Could not create login. Check email and try again."


def reset_student_password(student_id: str, school_id: str, new_password: str):
    student = get_student_by_id(student_id, school_id)
    if not student or not student.get("user_id"):
        return False, "No login account linked to this student."

    try:
        supabase_admin.auth.admin.update_user_by_id(
            student["user_id"],
            {"password": new_password},
        )
        return True, None
    except Exception:
        return False, "Password reset failed."
