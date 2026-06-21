from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort,
)
from controllers.auth_helpers import school_admin_required
from models.school_model import get_school_by_id
from models.teacher_model import (
    STAFF_STATUSES, DESIGNATIONS, DAYS_OF_WEEK,
    search_teachers, get_teacher_by_id, get_subjects, get_classes,
    get_assigned_subjects, get_assigned_classes, get_timetable, get_attendance,
    get_assigned_subject_ids, get_assigned_class_ids,
    create_teacher, update_teacher, deactivate_teacher, delete_teacher,
    add_timetable_slot, record_attendance,
    enable_teacher_login, reset_teacher_password,
)

teacher_bp = Blueprint("teachers", __name__)


def _admin_context(active_nav: str):
    return {
        "school": get_school_by_id(session["school_id"]),
        "school_id": session["school_id"],
        "full_name": session.get("full_name"),
        "role_label": "Admin",
        "active_nav": active_nav,
        "statuses": STAFF_STATUSES,
        "designations": DESIGNATIONS,
        "days_of_week": DAYS_OF_WEEK,
    }


def _form_data(form):
    return {
        "full_name": form.get("full_name", ""),
        "employee_id": form.get("employee_id", ""),
        "phone": form.get("phone", ""),
        "email": form.get("email", ""),
        "cnic": form.get("cnic", ""),
        "qualification": form.get("qualification", ""),
        "joining_date": form.get("joining_date") or None,
        "designation": form.get("designation", "Teacher"),
        "status": form.get("status", "active"),
    }


@teacher_bp.route("/")
@school_admin_required
def list_teachers():
    school_id = session["school_id"]
    query = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    teachers = search_teachers(school_id, query=query or None, status=status or None)

    ctx = _admin_context("teachers")
    ctx.update({"teachers": teachers, "query": query, "filter_status": status, "page_title": "Teacher & Staff Management"})
    return render_template("teachers/list.html", **ctx)


@teacher_bp.route("/add", methods=["GET", "POST"])
@school_admin_required
def add_teacher():
    school_id = session["school_id"]
    subjects = get_subjects(school_id)
    classes = get_classes(school_id)

    if request.method == "POST":
        data = _form_data(request.form)
        subject_ids = request.form.getlist("subject_ids")
        class_ids = request.form.getlist("class_ids")
        new_subjects = [s.strip() for s in request.form.get("new_subjects", "").split(",") if s.strip()]

        if not data["full_name"] or not data["employee_id"]:
            flash("Name and Employee ID are required.", "error")
        else:
            try:
                teacher = create_teacher(school_id, data, subject_ids, class_ids, new_subjects)
                if request.form.get("enable_login") == "on":
                    email = data.get("email") or request.form.get("login_email", "")
                    password = request.form.get("login_password", "")
                    if email and password:
                        _, err = enable_teacher_login(teacher["id"], school_id, email, password, data["full_name"])
                        if err:
                            flash(f"Staff saved, login failed: {err}", "error")
                        else:
                            flash("Teacher added with login enabled.", "success")
                            return redirect(url_for("teachers.view_teacher", teacher_id=teacher["id"]))
                flash(f"{data['full_name']} added successfully.", "success")
                return redirect(url_for("teachers.view_teacher", teacher_id=teacher["id"]))
            except Exception:
                flash("Could not add teacher. Check Employee ID is unique.", "error")

    ctx = _admin_context("teachers")
    ctx.update({
        "teacher": None, "subjects": subjects, "classes": classes,
        "assigned_subject_ids": [], "assigned_class_ids": [],
        "page_title": "Add Teacher / Staff",
        "form_action": url_for("teachers.add_teacher"),
    })
    return render_template("teachers/form.html", **ctx)


@teacher_bp.route("/<teacher_id>")
@school_admin_required
def view_teacher(teacher_id):
    school_id = session["school_id"]
    teacher = get_teacher_by_id(teacher_id, school_id)
    if not teacher:
        abort(404)

    ctx = _admin_context("teachers")
    ctx.update({
        "teacher": teacher,
        "subjects": get_assigned_subjects(teacher_id),
        "classes": get_assigned_classes(teacher_id),
        "timetable": get_timetable(teacher_id),
        "attendance": get_attendance(teacher_id),
        "all_subjects": get_subjects(school_id),
        "all_classes": get_classes(school_id),
        "page_title": teacher["full_name"],
    })
    return render_template("teachers/detail.html", **ctx)


@teacher_bp.route("/<teacher_id>/edit", methods=["GET", "POST"])
@school_admin_required
def edit_teacher(teacher_id):
    school_id = session["school_id"]
    teacher = get_teacher_by_id(teacher_id, school_id)
    if not teacher:
        abort(404)

    subjects = get_subjects(school_id)
    classes = get_classes(school_id)

    if request.method == "POST":
        data = _form_data(request.form)
        subject_ids = request.form.getlist("subject_ids")
        class_ids = request.form.getlist("class_ids")
        new_subjects = [s.strip() for s in request.form.get("new_subjects", "").split(",") if s.strip()]

        if not data["full_name"] or not data["employee_id"]:
            flash("Name and Employee ID are required.", "error")
        else:
            try:
                if update_teacher(teacher_id, school_id, data, subject_ids, class_ids, new_subjects):
                    flash("Teacher updated successfully.", "success")
                    return redirect(url_for("teachers.view_teacher", teacher_id=teacher_id))
            except Exception:
                flash("Could not update teacher.", "error")

    ctx = _admin_context("teachers")
    ctx.update({
        "teacher": teacher, "subjects": subjects, "classes": classes,
        "assigned_subject_ids": get_assigned_subject_ids(teacher_id),
        "assigned_class_ids": get_assigned_class_ids(teacher_id),
        "page_title": f"Edit — {teacher['full_name']}",
        "form_action": url_for("teachers.edit_teacher", teacher_id=teacher_id),
    })
    return render_template("teachers/form.html", **ctx)


@teacher_bp.route("/<teacher_id>/timetable", methods=["POST"])
@school_admin_required
def add_timetable(teacher_id):
    school_id = session["school_id"]
    data = {
        "class_id": request.form.get("class_id") or None,
        "subject_id": request.form.get("subject_id") or None,
        "day_of_week": request.form.get("day_of_week"),
        "start_time": request.form.get("start_time"),
        "end_time": request.form.get("end_time"),
        "room": request.form.get("room", ""),
    }
    if not all([data["day_of_week"], data["start_time"], data["end_time"]]):
        flash("Day and times are required for timetable.", "error")
    elif add_timetable_slot(teacher_id, school_id, data):
        flash("Timetable slot added.", "success")
    else:
        flash("Could not add timetable slot.", "error")
    return redirect(url_for("teachers.view_teacher", teacher_id=teacher_id))


@teacher_bp.route("/<teacher_id>/attendance", methods=["POST"])
@school_admin_required
def add_attendance(teacher_id):
    school_id = session["school_id"]
    data = {
        "date": request.form.get("date"),
        "status": request.form.get("status", "present"),
        "check_in": request.form.get("check_in") or None,
        "check_out": request.form.get("check_out") or None,
        "notes": request.form.get("notes", ""),
    }
    if not data["date"]:
        flash("Date is required.", "error")
    elif record_attendance(teacher_id, school_id, data):
        flash("Attendance recorded.", "success")
    else:
        flash("Could not record attendance.", "error")
    return redirect(url_for("teachers.view_teacher", teacher_id=teacher_id))


@teacher_bp.route("/<teacher_id>/enable-login", methods=["POST"])
@school_admin_required
def enable_login(teacher_id):
    school_id = session["school_id"]
    teacher = get_teacher_by_id(teacher_id, school_id)
    if not teacher:
        abort(404)
    email = request.form.get("email", "").strip() or (teacher.get("email") or "")
    password = request.form.get("password", "")
    _, err = enable_teacher_login(teacher_id, school_id, email, password, teacher["full_name"])
    flash(err or "Login enabled.", "error" if err else "success")
    return redirect(url_for("teachers.view_teacher", teacher_id=teacher_id))


@teacher_bp.route("/<teacher_id>/reset-password", methods=["POST"])
@school_admin_required
def reset_password(teacher_id):
    school_id = session["school_id"]
    pwd = request.form.get("new_password", "")
    if len(pwd) < 6:
        flash("Password must be at least 6 characters.", "error")
    else:
        ok, err = reset_teacher_password(teacher_id, school_id, pwd)
        flash(err or "Password reset.", "error" if err else "success")
    return redirect(url_for("teachers.view_teacher", teacher_id=teacher_id))


@teacher_bp.route("/<teacher_id>/delete", methods=["POST"])
@school_admin_required
def remove_teacher(teacher_id):
    school_id = session["school_id"]
    if request.form.get("action") == "delete":
        if delete_teacher(teacher_id, school_id):
            flash("Teacher record deleted.", "success")
            return redirect(url_for("teachers.list_teachers"))
        flash("Delete failed.", "error")
    else:
        if deactivate_teacher(teacher_id, school_id):
            flash("Staff account deactivated.", "success")
        else:
            flash("Deactivation failed.", "error")
    return redirect(url_for("teachers.view_teacher", teacher_id=teacher_id))
