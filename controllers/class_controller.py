from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort

from controllers.auth_helpers import school_admin_required
from models.school_model import get_school_by_id
from models.class_model import (
    list_classes,
    get_class_by_id,
    get_available_teachers,
    get_class_teachers,
    get_class_teacher_ids,
    create_class,
    update_class,
    delete_class,
    get_students_in_class,
    get_students_for_assignment,
    bulk_assign_students_to_class,
)
from models.attendance_model import get_daily_summary, get_monthly_report
from models.exam_model import list_exam_terms, get_term_results

class_bp = Blueprint("classes", __name__)


def _admin_ctx():
    school_id = session["school_id"]
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "full_name": session.get("full_name"),
        "role_label": "Admin",
        "active_nav": "classes",
    }


def _form_data(form):
    return {
        "name": form.get("name", ""),
        "grade": form.get("grade", ""),
        "section": form.get("section", ""),
    }


@class_bp.route("/")
@school_admin_required
def index():
    school_id = session["school_id"]
    query = request.args.get("q", "").strip()
    classes = list_classes(school_id, query or None)

    total_students = 0
    total_teachers = 0
    for cls in classes:
        total_students += len(get_students_in_class(cls["id"], school_id))
        total_teachers += len(get_class_teachers(cls["id"], school_id))

    ctx = _admin_ctx()
    ctx.update({
        "classes": classes,
        "query": query,
        "total_classes": len(classes),
        "total_students": total_students,
        "total_teacher_links": total_teachers,
        "page_title": "Class Management",
    })
    return render_template("classes/list.html", **ctx)


@class_bp.route("/add", methods=["GET", "POST"])
@school_admin_required
def add_class():
    school_id = session["school_id"]
    teachers = get_available_teachers(school_id)

    if request.method == "POST":
        data = _form_data(request.form)
        teacher_ids = request.form.getlist("teacher_ids")
        if not data["name"].strip() and not data["grade"].strip():
            flash("Class name or grade is required.", "error")
        else:
            try:
                created = create_class(school_id, data, teacher_ids)
                if created:
                    flash("Class created successfully.", "success")
                    return redirect(url_for("classes.view_class", class_id=created["id"]))
                flash("Could not create class.", "error")
            except Exception:
                flash("Could not create class. Check for duplicate class setup.", "error")

    ctx = _admin_ctx()
    ctx.update({
        "classroom": None,
        "teachers": teachers,
        "selected_teacher_ids": [],
        "form_action": url_for("classes.add_class"),
        "page_title": "Add Class",
    })
    return render_template("classes/form.html", **ctx)


@class_bp.route("/<class_id>")
@school_admin_required
def view_class(class_id):
    school_id = session["school_id"]
    classroom = get_class_by_id(class_id, school_id)
    if not classroom:
        abort(404)

    students = get_students_in_class(class_id, school_id)
    assigned_teachers = get_class_teachers(class_id, school_id)
    teacher_ids = get_class_teacher_ids(class_id)

    today = request.args.get("date", date.today().isoformat())
    year = request.args.get("year", type=int) or date.today().year
    month = request.args.get("month", type=int) or date.today().month
    attendance_rows = get_monthly_report(school_id, year, month, class_id=class_id)

    student_attendance = {}
    for row in attendance_rows:
        sid = row["student_id"]
        if sid not in student_attendance:
            student_attendance[sid] = {
                "student": row.get("student") or {},
                "present": 0,
                "absent": 0,
                "late": 0,
                "leave": 0,
                "total": 0,
            }
        student_attendance[sid]["total"] += 1
        status = row.get("status")
        if status in ("present", "absent", "late", "leave"):
            student_attendance[sid][status] += 1

    terms = list_exam_terms(school_id, class_id=class_id, limit=8)
    term_summaries = []
    for term in terms:
        results = get_term_results(term["id"], school_id)
        if not results:
            continue
        percentages = [float(r.get("percentage") or 0) for r in results]
        term_summaries.append({
            "term": term,
            "result_count": len(results),
            "avg_percentage": round(sum(percentages) / len(percentages), 2) if percentages else 0,
            "topper": results[0].get("student", {}) if results else {},
        })

    daily_summary = get_daily_summary(school_id, today)
    assignment_pool = get_students_for_assignment(school_id)

    ctx = _admin_ctx()
    ctx.update({
        "classroom": classroom,
        "students": students,
        "assigned_teachers": assigned_teachers,
        "teacher_ids": teacher_ids,
        "all_teachers": get_available_teachers(school_id),
        "student_attendance": list(student_attendance.values()),
        "daily_summary": daily_summary,
        "attendance_year": year,
        "attendance_month": month,
        "att_date": today,
        "term_summaries": term_summaries,
        "assignment_pool": assignment_pool,
        "page_title": classroom.get("label") or "Class",
    })
    return render_template("classes/detail.html", **ctx)


@class_bp.route("/<class_id>/edit", methods=["GET", "POST"])
@school_admin_required
def edit_class(class_id):
    school_id = session["school_id"]
    classroom = get_class_by_id(class_id, school_id)
    if not classroom:
        abort(404)

    teachers = get_available_teachers(school_id)
    selected_teacher_ids = get_class_teacher_ids(class_id)

    if request.method == "POST":
        data = _form_data(request.form)
        teacher_ids = request.form.getlist("teacher_ids")
        if not data["name"].strip() and not data["grade"].strip():
            flash("Class name or grade is required.", "error")
        else:
            try:
                updated = update_class(class_id, school_id, data, teacher_ids)
                if updated:
                    flash("Class updated successfully.", "success")
                    return redirect(url_for("classes.view_class", class_id=class_id))
                flash("Could not update class.", "error")
            except Exception:
                flash("Could not update class.", "error")

    ctx = _admin_ctx()
    ctx.update({
        "classroom": classroom,
        "teachers": teachers,
        "selected_teacher_ids": selected_teacher_ids,
        "form_action": url_for("classes.edit_class", class_id=class_id),
        "page_title": f"Edit Class — {classroom.get('label') or classroom.get('name')}",
    })
    return render_template("classes/form.html", **ctx)


@class_bp.route("/<class_id>/teachers", methods=["POST"])
@school_admin_required
def update_teachers(class_id):
    school_id = session["school_id"]
    if not get_class_by_id(class_id, school_id):
        abort(404)
    teacher_ids = request.form.getlist("teacher_ids")
    if update_class(class_id, school_id, get_class_by_id(class_id, school_id), teacher_ids):
        flash("Class teacher assignments updated.", "success")
    else:
        flash("Could not update teacher assignments.", "error")
    return redirect(url_for("classes.view_class", class_id=class_id))


@class_bp.route("/<class_id>/assign-students", methods=["POST"])
@school_admin_required
def assign_students(class_id):
    school_id = session["school_id"]
    if not get_class_by_id(class_id, school_id):
        abort(404)

    student_ids = request.form.getlist("student_ids")
    if not student_ids:
        flash("Select at least one student to assign.", "error")
        return redirect(url_for("classes.view_class", class_id=class_id))

    count = bulk_assign_students_to_class(school_id, class_id, student_ids)
    flash(f"Assigned {count} student(s) to this class.", "success" if count else "error")
    return redirect(url_for("classes.view_class", class_id=class_id))


@class_bp.route("/<class_id>/delete", methods=["POST"])
@school_admin_required
def remove_class(class_id):
    school_id = session["school_id"]
    ok, err = delete_class(class_id, school_id)
    if ok:
        flash("Class deleted.", "success")
        return redirect(url_for("classes.index"))
    flash(err or "Could not delete class.", "error")
    return redirect(url_for("classes.view_class", class_id=class_id))
