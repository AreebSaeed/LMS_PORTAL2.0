from datetime import date
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort, Response, jsonify,
)
from controllers.auth_helpers import school_admin_required, teacher_required
from models.school_model import get_school_by_id
from models.attendance_model import (
    ATTENDANCE_STATUSES,
    get_teacher_by_user_id, get_classes_for_teacher, get_all_classes,
    get_students_for_class, get_attendance_for_class_date, is_sheet_submitted,
    save_class_attendance, submit_class_attendance, admin_update_attendance,
    get_daily_report, get_monthly_report, get_daily_summary,
    get_absent_students, get_late_students, get_student_history,
    get_teacher_attendance_report, notify_parents_of_absence, export_csv_rows,
)
from models.student_model import get_student_by_id

attendance_bp = Blueprint("attendance", __name__)


def _admin_ctx(active="attendance"):
    return {
        "school": get_school_by_id(session["school_id"]),
        "school_id": session["school_id"],
        "full_name": session.get("full_name"),
        "role_label": "Admin",
        "active_nav": active,
        "statuses": ATTENDANCE_STATUSES,
    }


def _teacher_ctx():
    school_id = session["school_id"]
    teacher = get_teacher_by_user_id(session["user_id"], school_id)
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "full_name": session.get("full_name"),
        "teacher": teacher,
        "statuses": ATTENDANCE_STATUSES,
    }


def _class_params(form_or_args):
    class_id = form_or_args.get("class_id") or None
    class_grade = form_or_args.get("class_grade") or None
    section = form_or_args.get("section") or None
    att_date = form_or_args.get("date") or date.today().isoformat()
    return class_id, class_grade, section, att_date


# ── Teacher routes ──────────────────────────────────────────────

@attendance_bp.route("/teacher")
@teacher_required
def teacher_index():
    ctx = _teacher_ctx()
    teacher = ctx.get("teacher")
    classes = get_classes_for_teacher(session["school_id"], teacher["id"]) if teacher else get_all_classes(session["school_id"])
    ctx.update({"classes": classes, "page_title": "Mark Attendance", "today": date.today().isoformat()})
    return render_template("attendance/teacher_index.html", **ctx)


@attendance_bp.route("/teacher/mark", methods=["GET", "POST"])
@teacher_required
def teacher_mark():
    school_id = session["school_id"]
    class_id, class_grade, section, att_date = _class_params(request.args if request.method == "GET" else request.form)

    if not class_id and not class_grade:
        flash("Select a class to mark attendance.", "error")
        return redirect(url_for("attendance.teacher_index"))

    cls = None
    if class_id:
        from models.teacher_model import get_classes
        for c in get_classes(school_id):
            if c["id"] == class_id:
                cls = c
                class_grade = c.get("grade") or c.get("name")
                section = c.get("section")
                break

    students = get_students_for_class(school_id, class_id, class_grade, section)
    existing = get_attendance_for_class_date(school_id, att_date, class_id, class_grade, section)
    submitted = is_sheet_submitted(school_id, att_date, class_id, class_grade, section)

    if request.method == "POST":
        action = request.form.get("action", "save")
        marks = {sid: request.form.get(f"status_{sid}", "present") for sid in [s["id"] for s in students]}

        if action == "submit":
            ok, err = save_class_attendance(
                school_id, att_date, marks, session["user_id"],
                class_id, class_grade, section,
            )
            if ok and submit_class_attendance(school_id, att_date, class_id, class_grade, section):
                flash("Attendance submitted to admin.", "success")
            else:
                flash(err or "Could not submit attendance.", "error")
        else:
            ok, err = save_class_attendance(
                school_id, att_date, marks, session["user_id"],
                class_id, class_grade, section,
            )
            if ok:
                flash("Attendance saved.", "success")
            else:
                flash(err or "Could not save attendance.", "error")
        return redirect(url_for(
            "attendance.teacher_mark",
            class_id=class_id or "", class_grade=class_grade or "",
            section=section or "", date=att_date,
        ))

    ctx = _teacher_ctx()
    ctx.update({
        "students": students,
        "existing": existing,
        "submitted": submitted,
        "class_info": cls,
        "class_id": class_id,
        "class_grade": class_grade,
        "section": section,
        "att_date": att_date,
        "page_title": "Daily Attendance",
    })
    return render_template("attendance/teacher_mark.html", **ctx)


@attendance_bp.route("/teacher/mark/data")
@teacher_required
def teacher_mark_data():
    school_id = session["school_id"]
    class_id, class_grade, section, att_date = _class_params(request.args)

    if not class_id and not class_grade:
        return jsonify({"error": "Class is required."}), 400

    if class_id:
        from models.teacher_model import get_classes
        for c in get_classes(school_id):
            if c["id"] == class_id:
                class_grade = c.get("grade") or c.get("name")
                section = c.get("section")
                break

    existing = get_attendance_for_class_date(school_id, att_date, class_id, class_grade, section)
    submitted = is_sheet_submitted(school_id, att_date, class_id, class_grade, section)

    records = {sid: rec.get("status", "present") for sid, rec in existing.items()}

    return jsonify({
        "date": att_date,
        "submitted": submitted,
        "records": records,
    })


@attendance_bp.route("/teacher/class/<class_id>")
@teacher_required
def teacher_class_view(class_id):
    att_date = request.args.get("date", date.today().isoformat())
    school_id = session["school_id"]
    records = get_daily_report(school_id, att_date)
    records = [r for r in records if r.get("class_id") == class_id]
    ctx = _teacher_ctx()
    ctx.update({"records": records, "att_date": att_date, "class_id": class_id, "page_title": "Class Attendance"})
    return render_template("attendance/teacher_class.html", **ctx)


# ── Admin routes ────────────────────────────────────────────────

@attendance_bp.route("/admin")
@school_admin_required
def admin_dashboard():
    school_id = session["school_id"]
    att_date = request.args.get("date", date.today().isoformat())
    summary = get_daily_summary(school_id, att_date)
    absent = get_absent_students(school_id, att_date)
    late = get_late_students(school_id, att_date)
    teacher_att = get_teacher_attendance_report(school_id, att_date)
    classes = get_all_classes(school_id)

    ctx = _admin_ctx()
    ctx.update({
        "att_date": att_date,
        "summary": summary,
        "absent_students": absent,
        "late_students": late,
        "teacher_attendance": teacher_att,
        "classes": classes,
        "page_title": "Attendance Management",
    })
    return render_template("attendance/admin_dashboard.html", **ctx)


@attendance_bp.route("/admin/daily")
@school_admin_required
def admin_daily():
    school_id = session["school_id"]
    att_date = request.args.get("date", date.today().isoformat())
    class_id = request.args.get("class_id") or None
    section = request.args.get("section") or None
    records = get_daily_report(school_id, att_date, class_id, section)
    ctx = _admin_ctx()
    ctx.update({
        "records": records,
        "att_date": att_date,
        "classes": get_all_classes(school_id),
        "filter_class": class_id,
        "filter_section": section,
        "page_title": "Daily Attendance Report",
    })
    return render_template("attendance/admin_daily.html", **ctx)


@attendance_bp.route("/admin/monthly")
@school_admin_required
def admin_monthly():
    school_id = session["school_id"]
    today = date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))
    class_id = request.args.get("class_id") or None
    records = get_monthly_report(school_id, year, month, class_id)

    stats = {}
    for r in records:
        sid = r["student_id"]
        if sid not in stats:
            stats[sid] = {"student": r.get("student", {}), "present": 0, "absent": 0, "late": 0, "leave": 0, "total": 0}
        stats[sid]["total"] += 1
        stats[sid][r["status"]] = stats[sid].get(r["status"], 0) + 1

    ctx = _admin_ctx()
    ctx.update({
        "records": records,
        "monthly_stats": list(stats.values()),
        "year": year,
        "month": month,
        "classes": get_all_classes(school_id),
        "filter_class": class_id,
        "page_title": "Monthly Attendance Report",
    })
    return render_template("attendance/admin_monthly.html", **ctx)


@attendance_bp.route("/admin/student/<student_id>")
@school_admin_required
def student_history(student_id):
    school_id = session["school_id"]
    student = get_student_by_id(student_id, school_id)
    if not student:
        abort(404)
    history = get_student_history(student_id, school_id)
    ctx = _admin_ctx()
    ctx.update({"student": student, "history": history, "page_title": f"Attendance — {student['full_name']}"})
    return render_template("attendance/student_history.html", **ctx)


@attendance_bp.route("/admin/edit/<record_id>", methods=["POST"])
@school_admin_required
def admin_edit_record(record_id):
    school_id = session["school_id"]
    status = request.form.get("status")
    notes = request.form.get("notes", "")
    if admin_update_attendance(record_id, school_id, status, notes):
        flash("Attendance updated.", "success")
    else:
        flash("Update failed.", "error")
    return redirect(request.referrer or url_for("attendance.admin_dashboard"))


@attendance_bp.route("/admin/export")
@school_admin_required
def admin_export():
    school_id = session["school_id"]
    att_date = request.args.get("date")
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    csv_data = export_csv_rows(school_id, att_date, year, month)
    filename = f"attendance_{att_date or f'{year}-{month:02d}'}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@attendance_bp.route("/admin/notify-absent", methods=["POST"])
@school_admin_required
def admin_notify_absent():
    school_id = session["school_id"]
    att_date = request.form.get("date", date.today().isoformat())
    count, err = notify_parents_of_absence(school_id, att_date, session.get("user_id"))
    if err:
        flash(err, "error")
    else:
        flash(f"Sent {count} absence notification(s) to parents.", "success")
    return redirect(url_for("attendance.admin_dashboard", date=att_date))
