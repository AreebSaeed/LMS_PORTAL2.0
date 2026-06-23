from datetime import date
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort, Response,
)
from controllers.auth_helpers import student_required
from models.school_model import get_school_by_id
from models.student_model import get_student_by_user_id, get_academic_history
from models.student_portal_model import (
    get_dashboard_data,
    get_attendance_summary,
    get_daily_attendance,
    get_monthly_attendance,
    get_exam_results,
    get_grade_summary,
    get_upcoming_exams,
    get_announcements,
    get_class_announcements_for_student,
    get_subjects_for_student,
    get_fee_summary,
    get_study_materials,
    get_notifications,
    get_student_messages,
    send_student_message,
)
from models.timetable_model import (
    fetch_class_timetable,
    build_time_ranges,
    _class_label,
)
from models.class_model import get_class_by_id
from models.homework_model import (
    get_homework_for_student,
    get_homework_by_id,
    get_homework_submission,
    submit_homework,
    mark_homework_seen,
    upload_file,
)

student_portal_bp = Blueprint("student_portal", __name__)


def _load_student():
    student = get_student_by_user_id(session["user_id"], session["school_id"])
    if not student:
        abort(403)
    return student


def _ctx(active_nav: str, student=None):
    school_id = session["school_id"]
    student = student or _load_student()
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "student": student,
        "full_name": session.get("full_name"),
        "active_nav": active_nav,
    }


@student_portal_bp.route("/")
@student_required
def dashboard():
    student = _load_student()
    data = get_dashboard_data(student, session["school_id"])
    ctx = _ctx("dashboard", student)
    ctx.update({"page_title": "Student Dashboard", **data})
    return render_template("student_portal/dashboard.html", **ctx)


@student_portal_bp.route("/profile")
@student_required
def profile():
    student = _load_student()
    ctx = _ctx("profile", student)
    ctx.update({
        "academic_history": get_academic_history(student["id"]),
        "attendance_summary": get_attendance_summary(student["id"], session["school_id"]),
        "page_title": "My Profile",
    })
    return render_template("student_portal/profile.html", **ctx)


@student_portal_bp.route("/attendance")
@student_required
def attendance():
    student = _load_student()
    school_id = session["school_id"]
    today = date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))
    att_date = request.args.get("date", today.isoformat())
    view = request.args.get("view", "monthly")

    ctx = _ctx("attendance", student)
    ctx.update({
        "view": view,
        "att_date": att_date,
        "year": year,
        "month": month,
        "daily_record": get_daily_attendance(student["id"], school_id, att_date),
        "monthly_records": get_monthly_attendance(student["id"], school_id, year, month),
        "summary": get_attendance_summary(student["id"], school_id, year, month),
        "page_title": "My Attendance",
    })
    return render_template("student_portal/attendance.html", **ctx)


@student_portal_bp.route("/timetable")
@student_required
def timetable():
    student = _load_student()
    school_id = session["school_id"]
    raw = fetch_class_timetable(student.get("class_id"), school_id)
    class_opts = []
    if student.get("class_id"):
        cls = get_class_by_id(student["class_id"], school_id)
        if cls:
            class_opts = [{"id": cls["id"], "label": _class_label(cls)}]

    ctx = _ctx("timetable", student)
    ctx.update({
        "page_title": "Class Timetable",
        "tt_slots": raw,
        "tt_time_ranges": build_time_ranges(),
        "tt_class_options": class_opts,
        "tt_can_edit": False,
        "tt_title": "Class Timetable",
    })
    return render_template("student_portal/timetable.html", **ctx)


@student_portal_bp.route("/subjects")
@student_required
def subjects():
    student = _load_student()
    ctx = _ctx("subjects", student)
    ctx.update({
        "subjects": get_subjects_for_student(student, session["school_id"]),
        "page_title": "My Subjects",
    })
    return render_template("student_portal/subjects.html", **ctx)


@student_portal_bp.route("/homework")
@student_required
def homework():
    student = _load_student()
    ctx = _ctx("homework", student)
    ctx.update({
        "homework_list": get_homework_for_student(student, session["school_id"]),
        "page_title": "Homework",
    })
    return render_template("student_portal/homework.html", **ctx)


@student_portal_bp.route("/homework/<homework_id>", methods=["GET", "POST"])
@student_required
def homework_detail(homework_id):
    student = _load_student()
    school_id = session["school_id"]
    hw = get_homework_by_id(homework_id, school_id)
    if not hw:
        abort(404)

    enriched = get_homework_for_student(student, school_id, limit=100)
    hw_display = next((h for h in enriched if h["id"] == homework_id), None)
    if not hw_display:
        abort(403)

    if request.method == "GET":
        mark_homework_seen(homework_id, student["id"], school_id, session["user_id"])

    submission = get_homework_submission(homework_id, student["id"], school_id)
    has_submitted = submission and submission.get("submitted_at")

    if request.method == "POST":
        notes = request.form.get("notes", "")
        attachment_url = None
        attachment_name = None
        file = request.files.get("attachment")
        if file and file.filename:
            attachment_url = upload_file(
                school_id, f"submissions/{homework_id}", file.read(), file.filename, file.content_type
            )
            attachment_name = file.filename
        result, err = submit_homework(
            homework_id, student["id"], school_id, notes,
            attachment_url=attachment_url, attachment_name=attachment_name,
        )
        if err:
            flash(err, "error")
        else:
            flash("Homework submitted successfully.", "success")
            return redirect(url_for("student_portal.homework_detail", homework_id=homework_id))

    ctx = _ctx("homework", student)
    ctx.update({
        "homework": hw_display,
        "submission": submission if has_submitted else None,
        "page_title": hw["title"],
    })
    return render_template("student_portal/homework_detail.html", **ctx)


@student_portal_bp.route("/results")
@student_required
def results():
    student = _load_student()
    ctx = _ctx("results", student)
    ctx.update({
        "results": get_exam_results(student["id"], session["school_id"]),
        "grade_summary": get_grade_summary(student["id"], session["school_id"]),
        "page_title": "Exam Results",
    })
    return render_template("student_portal/results.html", **ctx)


@student_portal_bp.route("/exams")
@student_required
def exams():
    student = _load_student()
    ctx = _ctx("exams", student)
    ctx.update({
        "upcoming_exams": get_upcoming_exams(student, session["school_id"]),
        "page_title": "Upcoming Exams",
    })
    return render_template("student_portal/exams.html", **ctx)


@student_portal_bp.route("/fees")
@student_required
def fees():
    student = _load_student()
    summary = get_fee_summary(student, session["school_id"])
    ctx = _ctx("fees", student)
    ctx.update({"fee_summary": summary, "page_title": "Fee Status"})
    return render_template("student_portal/fees.html", **ctx)


@student_portal_bp.route("/fees/<fee_id>/challan")
@student_required
def fee_challan(fee_id):
    student = _load_student()
    school_id = session["school_id"]
    from models.fee_model import get_fee_record
    from models.challan_service import build_challan_context, generate_challan_pdf

    fee = get_fee_record(fee_id, school_id)
    if not fee:
        abort(404)
    sid = student["id"]
    if fee.get("student_id") not in (sid, student.get("user_id")):
        abort(403)
    if fee.get("is_void"):
        flash("This challan is no longer valid.", "error")
        return redirect(url_for("student_portal.fees"))

    school = get_school_by_id(school_id)
    if request.args.get("format") == "pdf":
        pdf_bytes = generate_challan_pdf(school, fee, student)
        num = fee.get("challan_number") or fee_id[:8]
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=challan_{num}.pdf"},
        )

    ctx = _ctx("fees", student)
    ctx.update({
        "challan": build_challan_context(school, fee, student),
        "back_url": url_for("student_portal.fees"),
        "pdf_url": url_for("student_portal.fee_challan", fee_id=fee_id, format="pdf"),
        "page_title": f"Challan {fee.get('challan_number', '')}",
    })
    return render_template("fees/challan_print.html", **ctx)


@student_portal_bp.route("/announcements")
@student_required
def announcements():
    student = _load_student()
    school_id = session["school_id"]
    ctx = _ctx("announcements", student)
    ctx.update({
        "school_announcements": get_announcements(school_id),
        "class_announcements": get_class_announcements_for_student(student, school_id),
        "page_title": "Announcements",
    })
    return render_template("student_portal/announcements.html", **ctx)


@student_portal_bp.route("/materials")
@student_required
def materials():
    student = _load_student()
    ctx = _ctx("materials", student)
    ctx.update({
        "materials": get_study_materials(student, session["school_id"]),
        "page_title": "Study Materials",
    })
    return render_template("student_portal/materials.html", **ctx)


@student_portal_bp.route("/notifications")
@student_required
def notifications():
    student = _load_student()
    ctx = _ctx("notifications", student)
    ctx.update({
        "notifications": get_notifications(student["id"]),
        "page_title": "Notifications",
    })
    return render_template("student_portal/notifications.html", **ctx)


@student_portal_bp.route("/messages", methods=["GET", "POST"])
@student_required
def messages():
    student = _load_student()
    school_id = session["school_id"]

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        if not subject or not message:
            flash("Subject and message are required.", "error")
        elif send_student_message(student["id"], school_id, subject, message):
            flash("Message sent to school.", "success")
            return redirect(url_for("student_portal.messages"))
        else:
            flash("Could not send message.", "error")

    ctx = _ctx("messages", student)
    ctx.update({
        "messages_list": get_student_messages(student["id"], school_id),
        "page_title": "Messages",
    })
    return render_template("student_portal/messages.html", **ctx)
