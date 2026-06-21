from datetime import date
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort, Response,
)
from controllers.auth_helpers import parent_required
from models.school_model import get_school_by_id
from models.parent_model import get_parent_by_user_id, get_linked_students, parent_has_student, get_notifications
from models.student_model import get_student_by_id
from models.parent_portal_model import (
    get_dashboard_data,
    get_attendance_summary,
    get_daily_attendance,
    get_monthly_attendance,
    get_fees_for_students,
    get_fee_by_id,
    ensure_receipt,
    get_exam_results_for_students,
    get_class_timetable,
    get_announcements,
    get_upcoming_exams,
    get_parent_messages,
    send_parent_message,
)
from models.homework_model import (
    get_homework_for_students,
    get_homework_for_student,
    get_homework_by_id,
    get_homework_submission,
    mark_homework_seen,
)

parent_portal_bp = Blueprint("parent_portal", __name__)


def _load_parent():
    parent = get_parent_by_user_id(session["user_id"], session["school_id"])
    if not parent:
        abort(403)
    return parent


def _ctx(active_nav: str, parent=None):
    school_id = session["school_id"]
    parent = parent or _load_parent()
    children = get_linked_students(parent["id"])
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "parent": parent,
        "children": children,
        "full_name": session.get("full_name"),
        "active_nav": active_nav,
    }


def _resolve_student(parent, school_id, req=None):
    req = req or request
    student_id = req.args.get("student_id") or req.form.get("student_id")
    children = get_linked_students(parent["id"])
    if not children:
        return None, children
    if student_id:
        if not parent_has_student(parent["id"], student_id):
            abort(403)
        student = get_student_by_id(student_id, school_id)
        return student, children
    return get_student_by_id(children[0]["id"], school_id), children


@parent_portal_bp.route("/")
@parent_required
def dashboard():
    parent = _load_parent()
    student_id = request.args.get("student_id")
    data = get_dashboard_data(parent["id"], session["school_id"], student_id)
    ctx = _ctx("dashboard", parent)
    ctx.update({
        "page_title": "Parent Dashboard",
        **data,
    })
    return render_template("parent_portal/dashboard.html", **ctx)


@parent_portal_bp.route("/children")
@parent_required
def children():
    parent = _load_parent()
    ctx = _ctx("children", parent)
    ctx["page_title"] = "My Children"
    return render_template("parent_portal/children.html", **ctx)


@parent_portal_bp.route("/children/<student_id>")
@parent_required
def child_profile(student_id):
    parent = _load_parent()
    school_id = session["school_id"]
    if not parent_has_student(parent["id"], student_id):
        abort(403)
    student = get_student_by_id(student_id, school_id)
    if not student:
        abort(404)
    ctx = _ctx("children", parent)
    ctx.update({
        "student": student,
        "attendance_summary": get_attendance_summary(student_id, school_id),
        "page_title": student["full_name"],
    })
    return render_template("parent_portal/child_profile.html", **ctx)


@parent_portal_bp.route("/attendance")
@parent_required
def attendance():
    parent = _load_parent()
    school_id = session["school_id"]
    student, children = _resolve_student(parent, school_id)
    today = date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))
    att_date = request.args.get("date", today.isoformat())
    view = request.args.get("view", "monthly")

    ctx = _ctx("attendance", parent)
    ctx.update({
        "student": student,
        "view": view,
        "att_date": att_date,
        "year": year,
        "month": month,
        "daily_record": get_daily_attendance(student["id"], school_id, att_date) if student else None,
        "monthly_records": get_monthly_attendance(student["id"], school_id, year, month) if student else [],
        "summary": get_attendance_summary(student["id"], school_id, year, month) if student else {},
        "page_title": "Attendance",
    })
    return render_template("parent_portal/attendance.html", **ctx)


@parent_portal_bp.route("/fees")
@parent_required
def fees():
    parent = _load_parent()
    children = get_linked_students(parent["id"])
    fee_records = get_fees_for_students(children, session["school_id"])
    paid = [f for f in fee_records if f.get("status") == "paid"]
    unpaid = [f for f in fee_records if f.get("status") in ("pending", "partial", "overdue")]

    ctx = _ctx("fees", parent)
    ctx.update({
        "fee_records": fee_records,
        "paid_fees": paid,
        "unpaid_fees": unpaid,
        "pending_total": sum(f["balance"] for f in unpaid),
        "page_title": "Fee Status",
    })
    return render_template("parent_portal/fees.html", **ctx)


@parent_portal_bp.route("/fees/<fee_id>/receipt")
@parent_required
def fee_receipt(fee_id):
    parent = _load_parent()
    school_id = session["school_id"]
    children = get_linked_students(parent["id"])
    fee = get_fee_by_id(fee_id, school_id)
    if not fee:
        abort(404)

    student = None
    for s in children:
        if s["id"] == fee["student_id"] or s.get("user_id") == fee["student_id"]:
            student = get_student_by_id(s["id"], school_id)
            break
    if not student:
        abort(403)

    receipt = ensure_receipt(fee, student, school_id)
    if not receipt:
        flash("Receipt available only for paid fees.", "error")
        return redirect(url_for("parent_portal.fees"))

    school = get_school_by_id(school_id)
    fmt = request.args.get("format", "html")
    if fmt == "text":
        lines = [
            f"FEE RECEIPT — {school['name'] if school else 'School'}",
            f"Receipt No: {receipt['receipt_number']}",
            f"Student: {student['full_name']}",
            f"Admission No: {student.get('admission_number', '—')}",
            f"Amount Paid: {receipt['amount_paid']}",
            f"Payment Date: {receipt.get('payment_date', '')[:10]}",
            f"Method: {receipt.get('payment_method', 'cash')}",
        ]
        return Response("\n".join(lines), mimetype="text/plain",
                        headers={"Content-Disposition": f"attachment; filename=receipt_{receipt['receipt_number']}.txt"})

    if fmt == "pdf":
        from models.fee_model import get_fee_record, generate_receipt_pdf
        fee_detail = get_fee_record(fee_id, school_id)
        if not fee_detail:
            abort(404)
        pdf_bytes = generate_receipt_pdf(school, fee_detail, receipt, student)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=receipt_{receipt['receipt_number']}.pdf"},
        )

    ctx = _ctx("fees", parent)
    ctx.update({
        "fee": fee,
        "receipt": receipt,
        "student": student,
        "page_title": f"Receipt {receipt['receipt_number']}",
    })
    return render_template("parent_portal/receipt.html", **ctx)


@parent_portal_bp.route("/homework")
@parent_required
def homework():
    parent = _load_parent()
    children = get_linked_students(parent["id"])
    ctx = _ctx("homework", parent)
    ctx.update({
        "homework_list": get_homework_for_students(children, session["school_id"], limit=30),
        "page_title": "Homework & Classwork",
    })
    return render_template("parent_portal/homework.html", **ctx)


@parent_portal_bp.route("/homework/<homework_id>")
@parent_required
def homework_detail(homework_id):
    parent = _load_parent()
    school_id = session["school_id"]
    student, children = _resolve_student(parent, school_id)
    if not student:
        flash("No linked children found.", "error")
        return redirect(url_for("parent_portal.homework"))

    hw = get_homework_by_id(homework_id, school_id)
    if not hw:
        abort(404)

    enriched = get_homework_for_student(student, school_id, limit=100)
    hw_display = next((h for h in enriched if h["id"] == homework_id), None)
    if not hw_display:
        abort(403)

    mark_homework_seen(homework_id, student["id"], school_id, session["user_id"])
    submission = get_homework_submission(homework_id, student["id"], school_id)
    has_submitted = submission and submission.get("submitted_at")

    ctx = _ctx("homework", parent)
    ctx.update({
        "homework": hw_display,
        "student": student,
        "submission": submission if has_submitted else None,
        "page_title": hw["title"],
    })
    return render_template("parent_portal/homework_detail.html", **ctx)


@parent_portal_bp.route("/results")
@parent_required
def results():
    parent = _load_parent()
    children = get_linked_students(parent["id"])
    ctx = _ctx("results", parent)
    ctx.update({
        "results": get_exam_results_for_students(children, session["school_id"]),
        "page_title": "Exam Results",
    })
    return render_template("parent_portal/results.html", **ctx)


@parent_portal_bp.route("/timetable")
@parent_required
def timetable():
    parent = _load_parent()
    student, children = _resolve_student(parent, session["school_id"])
    slots = get_class_timetable(student.get("class_id") if student else None, session["school_id"]) if student else []
    ctx = _ctx("timetable", parent)
    ctx.update({
        "student": student,
        "timetable": slots,
        "page_title": "Timetable",
    })
    return render_template("parent_portal/timetable.html", **ctx)


@parent_portal_bp.route("/announcements")
@parent_required
def announcements():
    parent = _load_parent()
    ctx = _ctx("announcements", parent)
    ctx.update({
        "announcements": get_announcements(session["school_id"]),
        "page_title": "Announcements",
    })
    return render_template("parent_portal/announcements.html", **ctx)


@parent_portal_bp.route("/notifications")
@parent_required
def notifications():
    parent = _load_parent()
    ctx = _ctx("notifications", parent)
    ctx.update({
        "notifications": get_notifications(parent["id"], limit=50),
        "page_title": "Notifications",
    })
    return render_template("parent_portal/notifications.html", **ctx)


@parent_portal_bp.route("/messages", methods=["GET", "POST"])
@parent_required
def messages():
    parent = _load_parent()
    school_id = session["school_id"]
    children = get_linked_students(parent["id"])

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        student_id = request.form.get("student_id") or None
        if not subject or not message:
            flash("Subject and message are required.", "error")
        elif student_id and not parent_has_student(parent["id"], student_id):
            abort(403)
        elif send_parent_message(parent["id"], school_id, subject, message, student_id):
            flash("Your message has been sent to the school.", "success")
            return redirect(url_for("parent_portal.messages"))
        else:
            flash("Could not send message. Please try again.", "error")

    ctx = _ctx("messages", parent)
    ctx.update({
        "messages_list": get_parent_messages(parent["id"], school_id),
        "page_title": "Messages & Complaints",
    })
    return render_template("parent_portal/messages.html", **ctx)
