import uuid
from datetime import date, datetime, timezone
from calendar import monthrange
from models.supabase_client import supabase_admin
from models.attendance_model import get_students_for_class
from models.student_model import get_student_by_id

PAYMENT_METHODS = [
    ("cash", "Cash"),
    ("bank_transfer", "Bank Transfer"),
    ("card", "Card"),
    ("cheque", "Cheque"),
    ("online", "Online"),
]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _fee_components(row: dict) -> dict:
    return {
        "tuition_fee": float(row.get("tuition_fee") or 0),
        "admission_fee": float(row.get("admission_fee") or 0),
        "annual_fee": float(row.get("annual_fee") or 0),
        "exam_fee": float(row.get("exam_fee") or 0),
        "transport_fee": float(row.get("transport_fee") or 0),
    }


def calc_total_amount(row: dict) -> float:
    parts = _fee_components(row)
    misc = float(row.get("misc_charges") or 0)
    subtotal = sum(parts.values()) + misc
    discount = float(row.get("discount") or 0)
    fine = float(row.get("fine") or 0)
    return max(subtotal - discount + fine, 0)


def calc_balance(row: dict) -> float:
    total = calc_total_amount(row) if row.get("amount") is None else float(row.get("amount") or 0)
    paid = float(row.get("amount_paid") or 0)
    return max(total - paid, 0)


def _derive_status(row: dict) -> str:
    total = float(row.get("amount") or calc_total_amount(row))
    paid = float(row.get("amount_paid") or 0)
    balance = max(total - paid, 0)
    due = row.get("due_date") or ""
    today = date.today().isoformat()
    if balance <= 0 and paid > 0:
        return "paid"
    if paid > 0 and balance > 0:
        return "partial"
    if due and due < today:
        return "overdue"
    return "pending"


def enrich_fee_record(row: dict, students_map: dict = None, classes_map: dict = None):
    student = None
    if students_map:
        student = students_map.get(row.get("student_id"))
    if not student and row.get("student_id"):
        student = _lookup_student(row["student_id"], row.get("school_id"))

    total = float(row.get("amount") or calc_total_amount(row))
    paid = float(row.get("amount_paid") or 0)
    balance = max(total - paid, 0)
    cls_label = "—"
    if classes_map and row.get("class_id"):
        cls = classes_map.get(row["class_id"], {})
        cls_label = cls.get("name") or cls.get("grade") or "—"
        if cls.get("section"):
            cls_label = f"{cls_label} — {cls['section']}"

    return {
        **row,
        **(_fee_components(row)),
        "student": student,
        "student_name": student.get("full_name") if student else "Unknown",
        "class_label": cls_label,
        "total_amount": total,
        "balance": balance,
        "remaining_dues": balance,
    }


def _lookup_student(student_id: str, school_id: str):
    student = get_student_by_id(student_id, school_id)
    if student:
        return student
    try:
        rows = (
            supabase_admin.table("students")
            .select("*")
            .eq("user_id", student_id)
            .eq("school_id", school_id)
            .limit(1)
            .execute()
            .data or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _load_students_map(student_ids: list, school_id: str) -> dict:
    if not student_ids:
        return {}
    smap = {}
    try:
        rows = (
            supabase_admin.table("students")
            .select("id, full_name, admission_number, roll_number, class_grade, section, class_id, user_id")
            .eq("school_id", school_id)
            .execute()
            .data or []
        )
        for s in rows:
            smap[s["id"]] = s
            if s.get("user_id"):
                smap[s["user_id"]] = s
    except Exception:
        pass
    for sid in student_ids:
        if sid not in smap:
            s = _lookup_student(sid, school_id)
            if s:
                smap[sid] = s
                smap[s["id"]] = s
    return smap


def _load_classes_map(class_ids: list, school_id: str) -> dict:
    if not class_ids:
        return {}
    try:
        rows = (
            supabase_admin.table("classes")
            .select("id, name, grade, section")
            .eq("school_id", school_id)
            .in_("id", list(class_ids))
            .execute()
            .data or []
        )
        return {c["id"]: c for c in rows}
    except Exception:
        return {}


def get_dashboard_stats(school_id: str):
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    try:
        rows = (
            supabase_admin.table("fee_records")
            .select("*")
            .eq("school_id", school_id)
            .execute()
            .data or []
        )
    except Exception:
        rows = []

    collected_month = 0.0
    pending_total = 0.0
    paid_count = 0
    unpaid_count = 0
    defaulter_count = 0

    for row in rows:
        enriched = enrich_fee_record(row)
        paid = float(row.get("amount_paid") or 0)
        balance = enriched["balance"]
        status = _derive_status({**row, "amount": enriched["total_amount"]})

        if row.get("paid_at") and str(row["paid_at"])[:10] >= month_start:
            collected_month += paid
        elif paid > 0:
            try:
                payments = (
                    supabase_admin.table("fee_payments")
                    .select("amount, payment_date")
                    .eq("fee_record_id", row["id"])
                    .gte("payment_date", f"{month_start}T00:00:00")
                    .execute()
                    .data or []
                )
                collected_month += sum(float(p.get("amount") or 0) for p in payments)
            except Exception:
                pass

        if status == "paid":
            paid_count += 1
        elif status in ("pending", "partial", "overdue"):
            unpaid_count += 1
            pending_total += balance
            if status == "overdue":
                defaulter_count += 1

    recent = list_fees(school_id, limit=10)
    return {
        "collected_month": collected_month,
        "pending_total": pending_total,
        "paid_count": paid_count,
        "unpaid_count": unpaid_count,
        "defaulter_count": defaulter_count,
        "recent_transactions": recent,
    }


def list_fee_structures(school_id: str):
    try:
        rows = (
            supabase_admin.table("fee_structures")
            .select("*")
            .eq("school_id", school_id)
            .order("created_at")
            .execute()
            .data or []
        )
    except Exception:
        return []

    class_ids = {r["class_id"] for r in rows if r.get("class_id")}
    cmap = _load_classes_map(class_ids, school_id)
    result = []
    for row in rows:
        cls = cmap.get(row.get("class_id"), {})
        result.append({
            **row,
            "class_label": cls.get("name") or cls.get("grade") or "School Default",
            "section": cls.get("section"),
            "monthly_total": (
                float(row.get("tuition_fee") or 0) + float(row.get("transport_fee") or 0)
            ),
        })
    return result


def get_fee_structure_by_id(structure_id: str, school_id: str):
    if not structure_id:
        return None
    try:
        result = (
            supabase_admin.table("fee_structures")
            .select("*")
            .eq("id", structure_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def get_fee_structure(school_id: str, class_id: str = None):
    try:
        if class_id:
            rows = (
                supabase_admin.table("fee_structures")
                .select("*")
                .eq("school_id", school_id)
                .eq("class_id", class_id)
                .limit(1)
                .execute()
                .data or []
            )
            if rows:
                return rows[0]
        rows = (
            supabase_admin.table("fee_structures")
            .select("*")
            .eq("school_id", school_id)
            .is_("class_id", "null")
            .limit(1)
            .execute()
            .data or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def save_fee_structure(school_id: str, data: dict, class_id: str = None):
    payload = {
        "school_id": school_id,
        "class_id": class_id,
        "name": (data.get("name") or "").strip() or None,
        "tuition_fee": float(data.get("tuition_fee") or 0),
        "admission_fee": float(data.get("admission_fee") or 0),
        "annual_fee": float(data.get("annual_fee") or 0),
        "exam_fee": float(data.get("exam_fee") or 0),
        "transport_fee": float(data.get("transport_fee") or 0),
        "is_active": data.get("is_active", True),
        "updated_at": _now_iso(),
    }
    existing = get_fee_structure(school_id, class_id)
    try:
        if existing:
            result = (
                supabase_admin.table("fee_structures")
                .update(payload)
                .eq("id", existing["id"])
                .execute()
            )
        else:
            result = supabase_admin.table("fee_structures").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


OPTIONAL_FEE_COLUMNS = (
    "fee_structure_id",
    "misc_charges",
    "is_void",
    "voided_at",
    "voided_by",
    "superseded_by_id",
    "reissued_from_id",
)


def _fee_record_student_id(student: dict) -> str:
    """Canonical student id for fee_records (students.id after module16 migration)."""
    return student["id"]


def _fee_student_id_candidates(student: dict) -> list:
    """Try students.id first; fall back to user_id for legacy FK on user_profiles."""
    ids = [student["id"]]
    uid = student.get("user_id")
    if uid and uid not in ids:
        ids.append(uid)
    return ids


def _friendly_insert_error(err: str) -> str:
    text = err or ""
    if "fee_records_student_id_fkey" in text or "user_profiles" in text:
        return (
            "student account is not linked for fee records — run "
            "sql/module16_fee_records_student_fk.sql in Supabase SQL editor"
        )
    if "Could not find the" in text and "column" in text:
        return "database schema is out of date — run sql/module16_fee_records_student_fk.sql"
    return text[:240] if len(text) > 240 else text


def _insert_fee_record(payload: dict):
    attempt = {k: v for k, v in payload.items() if v is not None}
    last_err = "Could not save fee record."
    optional_stripped = False
    while True:
        try:
            result = supabase_admin.table("fee_records").insert(attempt).execute()
            if result.data:
                return result.data[0], None
            return None, "Insert returned no data."
        except Exception as exc:
            last_err = str(exc)
            if not optional_stripped:
                optional_stripped = True
                for col in OPTIONAL_FEE_COLUMNS:
                    attempt.pop(col, None)
                if len(attempt) < len({k: v for k, v in payload.items() if v is not None}):
                    continue
            break
    return None, last_err


def _insert_fee_record_for_student(payload: dict, student: dict):
    last_err = "Could not save fee record."
    for sid in _fee_student_id_candidates(student):
        row, err = _insert_fee_record({**payload, "student_id": sid})
        if row:
            return row, None
        last_err = err or last_err
        err_text = str(err or "")
        if "fee_records_student_id_fkey" not in err_text and "user_profiles" not in err_text:
            break
    return None, last_err


def _next_challan_number(school_id: str, billing_month: date) -> str:
    year = billing_month.strftime("%Y")
    prefix = f"FEE-{year}"
    try:
        rows = (
            supabase_admin.table("fee_records")
            .select("challan_number")
            .eq("school_id", school_id)
            .like("challan_number", f"{prefix}%")
            .execute()
            .data or []
        )
        seq = len(rows) + 1
    except Exception:
        seq = 1
    return f"{prefix}-{seq:04d}"


def _next_receipt_number(school_id: str) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"RCP-{today}"
    try:
        rows = (
            supabase_admin.table("fee_receipts")
            .select("receipt_number")
            .eq("school_id", school_id)
            .like("receipt_number", f"{prefix}%")
            .execute()
            .data or []
        )
        seq = len(rows) + 1
    except Exception:
        seq = 1
    return f"{prefix}-{seq:04d}"


def generate_monthly_challans(
    school_id: str,
    class_id: str,
    billing_year: int,
    billing_month: int,
    user_id: str,
    include: dict = None,
    due_day: int = 10,
    structure_id: str = None,
):
    include = include or {
        "tuition": True, "transport": True,
        "admission": False, "annual": False, "exam": False,
    }
    billing_date = date(billing_year, billing_month, 1)
    last_day = monthrange(billing_year, billing_month)[1]
    due_date = date(billing_year, billing_month, min(due_day, last_day)).isoformat()
    billing_month_iso = billing_date.isoformat()

    structure = None
    if structure_id:
        structure = get_fee_structure_by_id(structure_id, school_id)
        if not structure:
            return 0, "Selected fee structure not found."
    if not structure:
        structure = get_fee_structure(school_id, class_id) or get_fee_structure(school_id, None)
    if not structure:
        return 0, "No fee structure found. Create a fee structure and select it when generating."

    students = get_students_for_class(school_id, class_id=class_id)
    if not students:
        return 0, "No active students found for this class."

    try:
        existing = (
            supabase_admin.table("fee_records")
            .select("student_id")
            .eq("school_id", school_id)
            .eq("billing_month", billing_month_iso)
            .eq("class_id", class_id)
            .eq("is_void", False)
            .execute()
            .data or []
        )
        existing_ids = {r["student_id"] for r in existing}
    except Exception:
        existing_ids = set()

    created = 0
    skipped_existing = 0
    failures = []

    for student in students:
        sid = _fee_record_student_id(student)
        lookup_ids = {sid, student.get("user_id")} - {None}
        if lookup_ids & existing_ids:
            skipped_existing += 1
            continue

        tuition = float(structure.get("tuition_fee") or 0) if include.get("tuition") else 0
        transport = float(structure.get("transport_fee") or 0) if include.get("transport") else 0
        admission = float(structure.get("admission_fee") or 0) if include.get("admission") else 0
        annual = float(structure.get("annual_fee") or 0) if include.get("annual") else 0
        exam = float(structure.get("exam_fee") or 0) if include.get("exam") else 0

        row = {
            "tuition_fee": tuition,
            "admission_fee": admission,
            "annual_fee": annual,
            "exam_fee": exam,
            "transport_fee": transport,
            "discount": 0,
            "fine": 0,
        }
        total = calc_total_amount(row)

        payload = {
            "school_id": school_id,
            "class_id": class_id,
            "fee_structure_id": structure.get("id"),
            "amount": total,
            "amount_paid": 0,
            "remaining_dues": total,
            "status": "pending",
            "due_date": due_date,
            "billing_month": billing_month_iso,
            "challan_number": _next_challan_number(school_id, billing_date),
            "recorded_by": user_id,
            "is_void": False,
            "misc_charges": 0,
            **row,
        }
        inserted, err = _insert_fee_record_for_student(payload, student)
        if inserted:
            created += 1
            existing_ids.update(lookup_ids)
        else:
            name = student.get("full_name") or "Student"
            failures.append(f"{name}: {_friendly_insert_error(err)}")

    if created == 0:
        if skipped_existing >= len(students):
            return 0, "All students in this class already have challans for this billing month."
        if failures:
            unique = list(dict.fromkeys(failures))
            hint = unique[0]
            if len(unique) > 1:
                hint += f" (+{len(unique) - 1} more)"
            if any("module16" in f for f in unique):
                return 0, (
                    "No challans could be saved. Your database still links fee records to "
                    "portal logins instead of student profiles. Run "
                    "sql/module16_fee_records_student_fk.sql in the Supabase SQL editor, then try again."
                )
            return 0, f"No challans could be saved. {hint}"
        return 0, "No new challans created (students may already have challans for this month)."
    return created, None


def list_fees(school_id: str, status: str = None, class_id: str = None,
              billing_month: str = None, limit=100, include_void: bool = False):
    try:
        q = (
            supabase_admin.table("fee_records")
            .select("*")
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if not include_void:
            q = q.eq("is_void", False)
        if status:
            q = q.eq("status", status)
        if class_id:
            q = q.eq("class_id", class_id)
        if billing_month:
            q = q.eq("billing_month", billing_month)
        rows = q.execute().data or []
    except Exception:
        if include_void:
            return []
        try:
            q = (
                supabase_admin.table("fee_records")
                .select("*")
                .eq("school_id", school_id)
                .order("created_at", desc=True)
                .limit(limit)
            )
            if status:
                q = q.eq("status", status)
            if class_id:
                q = q.eq("class_id", class_id)
            if billing_month:
                q = q.eq("billing_month", billing_month)
            rows = q.execute().data or []
        except Exception:
            return []

    student_ids = {r["student_id"] for r in rows}
    class_ids = {r["class_id"] for r in rows if r.get("class_id")}
    smap = _load_students_map(list(student_ids), school_id)
    cmap = _load_classes_map(class_ids, school_id)
    return [enrich_fee_record(r, smap, cmap) for r in rows]


def get_fee_record(fee_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("fee_records")
            .select("*")
            .eq("id", fee_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        row = result.data
    except Exception:
        return None
    if not row:
        return None
    smap = _load_students_map([row["student_id"]], school_id)
    cmap = _load_classes_map([row["class_id"]] if row.get("class_id") else [], school_id)
    return enrich_fee_record(row, smap, cmap)


def get_fee_payments(fee_id: str, school_id: str):
    try:
        return (
            supabase_admin.table("fee_payments")
            .select("*")
            .eq("fee_record_id", fee_id)
            .eq("school_id", school_id)
            .order("payment_date", desc=True)
            .execute()
            .data or []
        )
    except Exception:
        return []


def update_fee_adjustments(fee_id: str, school_id: str, discount: float = None, fine: float = None,
                           misc_charges: float = None, notes: str = None):
    fee = get_fee_record(fee_id, school_id)
    if not fee:
        return None, "Fee record not found."
    if fee.get("is_void"):
        return None, "This challan has been voided."

    payload = {}
    if discount is not None:
        payload["discount"] = max(float(discount), 0)
    if fine is not None:
        payload["fine"] = max(float(fine), 0)
    if misc_charges is not None:
        payload["misc_charges"] = max(float(misc_charges), 0)
    if notes is not None:
        payload["notes"] = notes.strip() or None

    updated = {**fee, **payload}
    total = calc_total_amount(updated)
    paid = float(fee.get("amount_paid") or 0)
    balance = max(total - paid, 0)
    payload["amount"] = total
    payload["remaining_dues"] = balance
    payload["status"] = _derive_status({**updated, "amount": total, "amount_paid": paid})

    try:
        result = (
            supabase_admin.table("fee_records")
            .update(payload)
            .eq("id", fee_id)
            .eq("school_id", school_id)
            .execute()
        )
        return result.data[0] if result.data else None, None
    except Exception:
        return None, "Could not update fee record."


def record_payment(fee_id: str, school_id: str, amount: float, payment_method: str,
                   user_id: str, notes: str = None):
    fee = get_fee_record(fee_id, school_id)
    if not fee:
        return None, "Fee record not found."

    amount = float(amount)
    if amount <= 0:
        return None, "Payment amount must be greater than zero."

    balance = fee["balance"]
    if amount > balance:
        return None, f"Payment exceeds remaining balance ({balance:.2f})."

    receipt_number = _next_receipt_number(school_id)
    payment_payload = {
        "school_id": school_id,
        "fee_record_id": fee_id,
        "amount": amount,
        "payment_method": payment_method or "cash",
        "payment_date": _now_iso(),
        "receipt_number": receipt_number,
        "recorded_by": user_id,
        "notes": (notes or "").strip() or None,
    }

    new_paid = float(fee.get("amount_paid") or 0) + amount
    total = fee["total_amount"]
    new_balance = max(total - new_paid, 0)
    status = _derive_status({"amount": total, "amount_paid": new_paid, "due_date": fee.get("due_date")})

    fee_update = {
        "amount_paid": new_paid,
        "remaining_dues": new_balance,
        "status": status,
        "payment_method": payment_method or "cash",
        "paid_at": _now_iso() if status == "paid" else fee.get("paid_at"),
    }

    try:
        supabase_admin.table("fee_payments").insert(payment_payload).execute()
        result = (
            supabase_admin.table("fee_records")
            .update(fee_update)
            .eq("id", fee_id)
            .execute()
        )
        student = fee.get("student") or {}
        receipt_payload = {
            "school_id": school_id,
            "fee_record_id": fee_id,
            "receipt_number": receipt_number,
            "student_id": student.get("id"),
            "amount_paid": amount,
            "payment_date": _now_iso(),
            "payment_method": payment_method or "cash",
            "issued_by": user_id,
        }
        try:
            supabase_admin.table("fee_receipts").insert(receipt_payload).execute()
        except Exception:
            pass

        return {
            "fee": result.data[0] if result.data else fee,
            "receipt_number": receipt_number,
            "payment": payment_payload,
        }, None
    except Exception:
        return None, "Could not record payment."


def get_receipt_for_fee(fee_id: str, school_id: str):
    try:
        rows = (
            supabase_admin.table("fee_receipts")
            .select("*")
            .eq("fee_record_id", fee_id)
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def get_parents_for_student(student_id: str, school_id: str):
    try:
        links = (
            supabase_admin.table("parent_student_links")
            .select("parent_id")
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .execute()
            .data or []
        )
        if not links:
            return []
        parent_ids = [l["parent_id"] for l in links]
        return (
            supabase_admin.table("parents")
            .select("id, full_name, email, phone, login_enabled")
            .in_("id", parent_ids)
            .execute()
            .data or []
        )
    except Exception:
        return []


def send_fee_reminder(fee_id: str, school_id: str, user_id: str, message: str = None):
    fee = get_fee_record(fee_id, school_id)
    if not fee:
        return False, "Fee record not found."

    student = fee.get("student")
    if not student:
        return False, "Student not found for this fee record."

    parents = get_parents_for_student(student["id"], school_id)
    if not parents:
        return False, "No parents linked to this student."

    balance = fee["balance"]
    default_msg = (
        f"Fee reminder: {student.get('full_name')} has outstanding dues of {balance:.2f}. "
        f"Challan {fee.get('challan_number') or fee['id'][:8]} — due {fee.get('due_date') or 'soon'}."
    )
    msg = (message or "").strip() or default_msg
    sent = 0
    for parent in parents:
        try:
            supabase_admin.table("parent_notifications").insert({
                "parent_id": parent["id"],
                "school_id": school_id,
                "subject": "Fee Payment Reminder",
                "message": msg,
                "sent_by": user_id,
            }).execute()
            supabase_admin.table("fee_reminders").insert({
                "school_id": school_id,
                "fee_record_id": fee_id,
                "parent_id": parent["id"],
                "student_id": student["id"],
                "message": msg,
                "sent_by": user_id,
            }).execute()
            sent += 1
        except Exception:
            pass

    if sent == 0:
        return False, "Could not send reminders."
    return True, f"Reminder sent to {sent} parent(s)."


def send_bulk_reminders(school_id: str, user_id: str, status: str = "overdue"):
    fees = list_fees(school_id, status=status, limit=200)
    fees = [f for f in fees if f["balance"] > 0]
    total = 0
    for fee in fees:
        ok, _ = send_fee_reminder(fee["id"], school_id, user_id)
        if ok:
            total += 1
    return total


def get_class_challan_summary(school_id: str, class_id: str = None, billing_month: str = None):
    """Counts per class for challan tracking dashboard."""
    fees = list_fees(school_id, class_id=class_id, billing_month=billing_month, limit=500)
    by_class = {}
    for f in fees:
        cid = f.get("class_id") or "none"
        label = f.get("class_label") or "Unassigned"
        if cid not in by_class:
            by_class[cid] = {"class_id": cid, "label": label, "total": 0, "paid": 0, "pending": 0, "amount_due": 0.0}
        by_class[cid]["total"] += 1
        if f.get("status") == "paid":
            by_class[cid]["paid"] += 1
        else:
            by_class[cid]["pending"] += 1
            by_class[cid]["amount_due"] += float(f.get("balance") or 0)
    return sorted(by_class.values(), key=lambda x: x["label"])


def reissue_challan(fee_id: str, school_id: str, user_id: str, data: dict = None):
    """Void the current challan and create a new one with updated amounts."""
    data = data or {}
    fee = get_fee_record(fee_id, school_id)
    if not fee:
        return None, "Challan not found."
    if fee.get("is_void"):
        return None, "This challan is already void."
    if float(fee.get("amount_paid") or 0) > 0:
        return None, "Cannot reissue a challan that has payments. Adjust the existing challan instead."

    billing_date = date.today()
    if fee.get("billing_month"):
        try:
            billing_date = datetime.strptime(str(fee["billing_month"])[:10], "%Y-%m-%d").date()
        except ValueError:
            pass

    discount = float(data.get("discount", fee.get("discount") or 0))
    fine = float(data.get("fine", fee.get("fine") or 0))
    misc = float(data.get("misc_charges", fee.get("misc_charges") or 0))
    due_date = data.get("due_date") or fee.get("due_date")
    notes = data.get("notes", fee.get("notes"))

    row = {
        "tuition_fee": fee.get("tuition_fee", 0),
        "admission_fee": fee.get("admission_fee", 0),
        "annual_fee": fee.get("annual_fee", 0),
        "exam_fee": fee.get("exam_fee", 0),
        "transport_fee": fee.get("transport_fee", 0),
        "discount": discount,
        "fine": fine,
        "misc_charges": misc,
    }
    total = calc_total_amount(row)

    try:
        void_result = (
            supabase_admin.table("fee_records")
            .update({
                "is_void": True,
                "voided_at": _now_iso(),
                "voided_by": user_id,
                "notes": ((fee.get("notes") or "").strip() + " [Voided — reissued]").strip(),
            })
            .eq("id", fee_id)
            .eq("school_id", school_id)
            .execute()
        )
        if not void_result.data:
            return None, "Could not void the previous challan."
    except Exception:
        return None, "Could not void the previous challan."

    new_payload = {
        "school_id": school_id,
        "student_id": fee["student_id"],
        "class_id": fee.get("class_id"),
        "fee_structure_id": fee.get("fee_structure_id"),
        "amount": total,
        "amount_paid": 0,
        "remaining_dues": total,
        "status": "pending",
        "due_date": due_date,
        "billing_month": fee.get("billing_month"),
        "challan_number": _next_challan_number(school_id, billing_date),
        "recorded_by": user_id,
        "reissued_from_id": fee_id,
        "is_void": False,
        "notes": (notes or "").strip() or None,
        **row,
    }
    try:
        result = supabase_admin.table("fee_records").insert(new_payload).execute()
        if not result.data:
            return None, "Could not create reissued challan."
        new_id = result.data[0]["id"]
        supabase_admin.table("fee_records").update({"superseded_by_id": new_id}).eq("id", fee_id).execute()
        return get_fee_record(new_id, school_id), None
    except Exception:
        return None, "Could not create reissued challan."


def generate_receipt_pdf(school: dict, fee: dict, receipt: dict, student: dict) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, school.get("name", "School") if school else "School", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "FEE PAYMENT RECEIPT", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 11)
    meta = [
        f"Receipt No: {receipt.get('receipt_number', '')}",
        f"Date: {str(receipt.get('payment_date', ''))[:10]}",
        f"Challan No: {fee.get('challan_number') or '—'}",
        f"Student: {student.get('full_name', '')}",
        f"Admission No: {student.get('admission_number', '—')}",
        f"Class: {student.get('class_grade', '')}-{student.get('section') or ''}",
    ]
    for line in meta:
        pdf.cell(0, 8, line, ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(100, 8, "Fee Component", border=1)
    pdf.cell(50, 8, "Amount", border=1, ln=True)
    pdf.set_font("Helvetica", "", 10)

    components = [
        ("Tuition Fee", fee.get("tuition_fee")),
        ("Admission Fee", fee.get("admission_fee")),
        ("Annual Fee", fee.get("annual_fee")),
        ("Exam Fee", fee.get("exam_fee")),
        ("Transport Fee", fee.get("transport_fee")),
        ("Discount", -float(fee.get("discount") or 0)),
        ("Fine / Late Fee", fee.get("fine")),
    ]
    for label, val in components:
        if val and float(val) != 0:
            pdf.cell(100, 8, label, border=1)
            pdf.cell(50, 8, f"{float(val):.2f}", border=1, ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"Total Fee: {fee.get('total_amount', fee.get('amount', 0)):.2f}", ln=True)
    pdf.cell(0, 8, f"Amount Paid (this receipt): {float(receipt.get('amount_paid', 0)):.2f}", ln=True)
    pdf.cell(0, 8, f"Total Paid: {float(fee.get('amount_paid', 0)):.2f}", ln=True)
    pdf.cell(0, 8, f"Remaining Dues: {fee.get('balance', 0):.2f}", ln=True)
    pdf.cell(0, 8, f"Payment Method: {(receipt.get('payment_method') or 'cash').replace('_', ' ').title()}", ln=True)
    pdf.cell(0, 8, f"Status: {(fee.get('status') or '').title()}", ln=True)

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, "Computer-generated receipt. Contact school office for queries.", ln=True, align="C")
    return pdf.output()
