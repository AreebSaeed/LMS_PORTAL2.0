from datetime import date
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort,
)
from controllers.auth_helpers import teacher_required
from models.school_model import get_school_by_id
from models.teacher_model import (
    get_teacher_by_user_id, get_assigned_classes, get_assigned_subjects,
    get_timetable, teacher_owns_class, get_subjects,
)
from models.teacher_portal_model import (
    get_dashboard_data,
    get_todays_schedule,
    get_exams_for_teacher,
    get_exam_results_for_exam,
    save_exam_marks,
    get_school_announcements,
    get_class_announcements,
    create_class_announcement,
    get_students_for_teacher_class,
)
from models.homework_model import (
    HW_TYPES,
    upload_file,
    get_teacher_homework,
    create_homework,
    get_homework_by_id,
    get_homework_submissions,
    get_homework_views,
    record_teacher_submission,
    add_teacher_comment,
)
from models.attendance_model import get_students_for_class
from models.timetable_model import (
    normalize_teacher_slots,
    build_time_ranges,
    class_filter_options,
    COLOR_OPTIONS,
)

teacher_portal_bp = Blueprint("teacher_portal", __name__)


def _load_teacher():
    teacher = get_teacher_by_user_id(session["user_id"], session["school_id"])
    if not teacher:
        abort(403)
    return teacher


def _ctx(active_nav: str, teacher=None):
    school_id = session["school_id"]
    teacher = teacher or _load_teacher()
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "teacher": teacher,
        "full_name": session.get("full_name"),
        "active_nav": active_nav,
        "classes": get_assigned_classes(teacher["id"]),
        "subjects": get_assigned_subjects(teacher["id"]),
    }


@teacher_portal_bp.route("/")
@teacher_required
def dashboard():
    teacher = _load_teacher()
    data = get_dashboard_data(teacher["id"], session["school_id"], session["user_id"])
    ctx = _ctx("dashboard", teacher)
    ctx.update({"page_title": "Teacher Dashboard", **data})
    return render_template("teacher_portal/dashboard.html", **ctx)


@teacher_portal_bp.route("/classes")
@teacher_required
def classes():
    teacher = _load_teacher()
    ctx = _ctx("classes", teacher)
    ctx.update({
        "assigned_classes": get_assigned_classes(teacher["id"]),
        "page_title": "My Classes",
    })
    return render_template("teacher_portal/classes.html", **ctx)


@teacher_portal_bp.route("/subjects")
@teacher_required
def subjects():
    teacher = _load_teacher()
    ctx = _ctx("subjects", teacher)
    ctx.update({
        "assigned_subjects": get_assigned_subjects(teacher["id"]),
        "page_title": "My Subjects",
    })
    return render_template("teacher_portal/subjects.html", **ctx)


@teacher_portal_bp.route("/students")
@teacher_required
def students():
    teacher = _load_teacher()
    school_id = session["school_id"]
    class_id = request.args.get("class_id")
    assigned = get_assigned_classes(teacher["id"])

    if not class_id and assigned:
        class_id = assigned[0]["id"]

    student_list = []
    selected_class = None
    if class_id:
        if not teacher_owns_class(teacher["id"], class_id):
            abort(403)
        student_list = get_students_for_teacher_class(teacher["id"], school_id, class_id)
        selected_class = next((c for c in assigned if c["id"] == class_id), None)

    ctx = _ctx("students", teacher)
    ctx.update({
        "students": student_list,
        "selected_class": selected_class,
        "class_id": class_id,
        "page_title": "Student List",
    })
    return render_template("teacher_portal/students.html", **ctx)


@teacher_portal_bp.route("/timetable")
@teacher_required
def timetable():
    teacher = _load_teacher()
    raw = get_timetable(teacher["id"])
    slots = normalize_teacher_slots(raw, teacher_name=teacher.get("full_name"))
    assigned_classes = get_assigned_classes(teacher["id"])
    class_opts = class_filter_options(slots) or [
        {"id": c["id"], "label": (c.get("name") or c.get("grade") or "Class") + (f" — {c['section']}" if c.get("section") else "")}
        for c in assigned_classes
    ]

    ctx = _ctx("timetable", teacher)
    ctx.update({
        "page_title": "Class Timetable",
        "tt_slots": slots,
        "tt_time_ranges": build_time_ranges(),
        "tt_class_options": class_opts,
        "tt_colors": COLOR_OPTIONS,
        "tt_can_edit": False,
        "tt_title": "Class Timetable",
    })
    return render_template("teacher_portal/timetable.html", **ctx)


@teacher_portal_bp.route("/homework", methods=["GET", "POST"])
@teacher_required
def homework():
    teacher = _load_teacher()
    school_id = session["school_id"]

    if request.method == "POST":
        class_id = request.form.get("class_id") or None
        if class_id and not teacher_owns_class(teacher["id"], class_id):
            abort(403)
        data = {
            "class_id": class_id,
            "subject_id": request.form.get("subject_id") or None,
            "title": request.form.get("title", ""),
            "description": request.form.get("description", ""),
            "due_date": request.form.get("due_date") or None,
            "hw_type": request.form.get("hw_type") or "homework",
            "submission_enabled": request.form.get("submission_enabled") == "on",
        }
        attachment_url = None
        attachment_name = None
        file = request.files.get("attachment")
        if file and file.filename:
            attachment_url = upload_file(
                school_id, "assignments", file.read(), file.filename, file.content_type
            )
            attachment_name = file.filename
            if not attachment_url:
                flash("Could not upload attachment. Check storage bucket 'homework-attachments'.", "error")
                return redirect(url_for("teacher_portal.homework"))

        if not data["title"].strip():
            flash("Homework title is required.", "error")
        elif create_homework(
            school_id, teacher["id"], session["user_id"], data,
            attachment_url=attachment_url, attachment_name=attachment_name,
        ):
            flash("Homework assigned successfully.", "success")
            return redirect(url_for("teacher_portal.homework"))
        else:
            flash("Could not create homework.", "error")

    ctx = _ctx("homework", teacher)
    ctx.update({
        "homework_list": get_teacher_homework(teacher["id"], school_id, session["user_id"], limit=30),
        "all_subjects": get_subjects(school_id),
        "hw_types": HW_TYPES,
        "page_title": "Homework & Classwork",
    })
    return render_template("teacher_portal/homework.html", **ctx)


@teacher_portal_bp.route("/homework/<homework_id>/submissions", methods=["GET", "POST"])
@teacher_required
def homework_submissions(homework_id):
    teacher = _load_teacher()
    school_id = session["school_id"]
    hw = get_homework_by_id(homework_id, school_id)
    if not hw:
        abort(404)
    if hw.get("class_id") and not teacher_owns_class(teacher["id"], hw["class_id"]):
        if hw.get("teacher_id") != teacher["id"]:
            abort(403)

    if request.method == "POST":
        action = request.form.get("action", "record")
        student_id = request.form.get("student_id")
        if action == "comment":
            comment = request.form.get("teacher_comment", "").strip()
            if student_id and comment and add_teacher_comment(homework_id, student_id, school_id, comment):
                flash("Comment saved.", "success")
            else:
                flash("Could not save comment.", "error")
        else:
            notes = request.form.get("notes", "")
            status = request.form.get("status", "submitted")
            if record_teacher_submission(homework_id, school_id, student_id, notes, status):
                flash("Submission recorded.", "success")
            else:
                flash("Could not record submission.", "error")
        return redirect(url_for("teacher_portal.homework_submissions", homework_id=homework_id))

    class_students = []
    if hw.get("class_id"):
        class_students = get_students_for_class(school_id, class_id=hw["class_id"])

    enriched = get_teacher_homework(teacher["id"], school_id, session["user_id"], limit=100)
    hw_display = next((h for h in enriched if h["id"] == homework_id), hw)

    ctx = _ctx("homework", teacher)
    ctx.update({
        "homework": hw_display,
        "submissions": get_homework_submissions(homework_id, school_id),
        "views": get_homework_views(homework_id, school_id),
        "class_students": class_students,
        "page_title": f"Submissions — {hw['title']}",
    })
    return render_template("teacher_portal/homework_submissions.html", **ctx)


@teacher_portal_bp.route("/marks", methods=["GET", "POST"])
@teacher_required
def marks():
    return redirect(url_for("exams.index"))


@teacher_portal_bp.route("/announcements", methods=["GET", "POST"])
@teacher_required
def announcements():
    teacher = _load_teacher()
    school_id = session["school_id"]

    if request.method == "POST":
        class_id = request.form.get("class_id") or None
        if class_id and not teacher_owns_class(teacher["id"], class_id):
            abort(403)
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title:
            flash("Title is required.", "error")
        elif create_class_announcement(teacher["id"], school_id, class_id, title, body):
            flash("Class announcement posted.", "success")
            return redirect(url_for("teacher_portal.announcements"))
        else:
            flash("Could not post announcement.", "error")

    ctx = _ctx("announcements", teacher)
    ctx.update({
        "school_announcements": get_school_announcements(school_id, limit=15),
        "my_announcements": get_class_announcements(teacher["id"], school_id),
        "page_title": "Announcements",
    })
    return render_template("teacher_portal/announcements.html", **ctx)
