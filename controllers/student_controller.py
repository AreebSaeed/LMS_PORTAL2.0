from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort,
)
from controllers.auth_helpers import school_admin_required
from models.school_model import get_school_by_id
from models.student_model import (
    STUDENT_STATUSES, GENDERS,
    search_students, get_student_by_id, get_student_documents,
    get_academic_history, get_classes_for_school, get_distinct_class_sections,
    create_student, update_student, update_student_status, delete_student,
    update_student_class_assignment,
    upload_file, update_student_photo, add_document,
    enable_student_login, reset_student_password,
)

student_bp = Blueprint("students", __name__)


def _admin_context(active_nav: str):
    school_id = session["school_id"]
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "full_name": session.get("full_name"),
        "role_label": "Admin",
        "active_nav": active_nav,
        "statuses": STUDENT_STATUSES,
        "genders": GENDERS,
    }


def _form_data(form):
    return {
        "full_name": form.get("full_name", ""),
        "admission_number": form.get("admission_number", ""),
        "roll_number": form.get("roll_number", ""),
        "date_of_birth": form.get("date_of_birth") or None,
        "gender": form.get("gender") or None,
        "class_id": form.get("class_id") or None,
        "class_grade": form.get("class_grade", ""),
        "section": form.get("section", ""),
        "batch_session": form.get("batch_session", ""),
        "address": form.get("address", ""),
        "contact_number": form.get("contact_number", ""),
        "parent_name": form.get("parent_name", ""),
        "parent_cnic": form.get("parent_cnic", ""),
        "emergency_contact": form.get("emergency_contact", ""),
        "previous_school": form.get("previous_school", ""),
        "status": form.get("status", "active"),
    }


@student_bp.route("/")
@school_admin_required
def list_students():
    school_id = session["school_id"]
    query = request.args.get("q", "").strip()
    class_grade = request.args.get("class", "").strip()
    section = request.args.get("section", "").strip()
    status = request.args.get("status", "").strip()

    students = search_students(
        school_id,
        query=query or None,
        class_grade=class_grade or None,
        section=section or None,
        status=status or None,
    )
    grades, sections = get_distinct_class_sections(school_id)

    ctx = _admin_context("students")
    ctx.update({
        "students": students,
        "query": query,
        "filter_class": class_grade,
        "filter_section": section,
        "filter_status": status,
        "class_grades": grades,
        "sections": sections,
        "page_title": "Student Management",
    })
    return render_template("students/list.html", **ctx)


@student_bp.route("/add", methods=["GET", "POST"])
@school_admin_required
def add_student():
    school_id = session["school_id"]
    classes = get_classes_for_school(school_id)

    if request.method == "POST":
        data = _form_data(request.form)
        if not data["full_name"] or not data["admission_number"]:
            flash("Student name and admission number are required.", "error")
        else:
            try:
                student = create_student(school_id, data)
                photo = request.files.get("photo")
                if photo and photo.filename:
                    url = upload_file(
                        school_id, student["id"], photo.read(),
                        photo.filename, photo.content_type,
                    )
                    if url:
                        update_student_photo(student["id"], school_id, url)
                    else:
                        flash("Student saved, but photo upload failed. Check Storage bucket.", "error")
                docs = request.files.getlist("documents")
                for doc in docs:
                    if doc and doc.filename:
                        url = upload_file(
                            school_id, student["id"], doc.read(),
                            doc.filename, doc.content_type,
                        )
                        if url:
                            add_document(student["id"], school_id, doc.filename, url)
                flash(f"Student {data['full_name']} added successfully.", "success")
                return redirect(url_for("students.view_student", student_id=student["id"]))
            except Exception:
                flash("Could not add student. Check admission number is unique.", "error")

    ctx = _admin_context("students")
    ctx.update({
        "student": None,
        "classes": classes,
        "page_title": "Add New Student",
        "form_action": url_for("students.add_student"),
    })
    return render_template("students/form.html", **ctx)


@student_bp.route("/<student_id>")
@school_admin_required
def view_student(student_id):
    school_id = session["school_id"]
    student = get_student_by_id(student_id, school_id)
    if not student:
        abort(404)

    ctx = _admin_context("students")
    ctx.update({
        "student": student,
        "documents": get_student_documents(student_id),
        "academic_history": get_academic_history(student_id),
        "classes": get_classes_for_school(school_id),
        "page_title": student["full_name"],
    })
    return render_template("students/detail.html", **ctx)


@student_bp.route("/<student_id>/edit", methods=["GET", "POST"])
@school_admin_required
def edit_student(student_id):
    school_id = session["school_id"]
    student = get_student_by_id(student_id, school_id)
    if not student:
        abort(404)

    classes = get_classes_for_school(school_id)

    if request.method == "POST":
        data = _form_data(request.form)
        if not data["full_name"] or not data["admission_number"]:
            flash("Student name and admission number are required.", "error")
        else:
            try:
                updated = update_student(student_id, school_id, data)
                if updated:
                    photo = request.files.get("photo")
                    if photo and photo.filename:
                        url = upload_file(
                            school_id, student_id, photo.read(),
                            photo.filename, photo.content_type,
                        )
                        if url:
                            update_student_photo(student_id, school_id, url)
                    docs = request.files.getlist("documents")
                    for doc in docs:
                        if doc and doc.filename:
                            url = upload_file(
                                school_id, student_id, doc.read(),
                                doc.filename, doc.content_type,
                            )
                            if url:
                                add_document(student_id, school_id, doc.filename, url)
                    flash("Student updated successfully.", "success")
                    return redirect(url_for("students.view_student", student_id=student_id))
            except Exception:
                flash("Could not update student.", "error")
        student = get_student_by_id(student_id, school_id)

    ctx = _admin_context("students")
    ctx.update({
        "student": student,
        "classes": classes,
        "page_title": f"Edit — {student['full_name']}",
        "form_action": url_for("students.edit_student", student_id=student_id),
    })
    return render_template("students/form.html", **ctx)


@student_bp.route("/<student_id>/status", methods=["POST"])
@school_admin_required
def set_status(student_id):
    school_id = session["school_id"]
    status = request.form.get("status", "")
    if status not in STUDENT_STATUSES:
        flash("Invalid status.", "error")
    else:
        result = update_student_status(student_id, school_id, status)
        if result:
            flash(f"Student marked as {status}.", "success")
        else:
            flash("Could not update status.", "error")
    return redirect(url_for("students.view_student", student_id=student_id))


@student_bp.route("/<student_id>/assign-class", methods=["POST"])
@school_admin_required
def assign_class(student_id):
    school_id = session["school_id"]
    class_id = request.form.get("class_id") or None
    updated = update_student_class_assignment(student_id, school_id, class_id)
    if updated:
        flash("Student class assignment updated.", "success")
    else:
        flash("Could not update class assignment.", "error")
    return redirect(url_for("students.view_student", student_id=student_id))


@student_bp.route("/<student_id>/delete", methods=["POST"])
@school_admin_required
def remove_student(student_id):
    school_id = session["school_id"]
    action = request.form.get("action", "deactivate")

    if action == "delete":
        if delete_student(student_id, school_id):
            flash("Student record deleted.", "success")
            return redirect(url_for("students.list_students"))
        flash("Could not delete student.", "error")
    else:
        result = update_student_status(student_id, school_id, "inactive")
        if result:
            flash("Student deactivated.", "success")
        else:
            flash("Could not deactivate student.", "error")
        return redirect(url_for("students.view_student", student_id=student_id))

    return redirect(url_for("students.view_student", student_id=student_id))


@student_bp.route("/<student_id>/enable-login", methods=["POST"])
@school_admin_required
def enable_login(student_id):
    school_id = session["school_id"]
    student = get_student_by_id(student_id, school_id)
    if not student:
        abort(404)
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    _, err = enable_student_login(student_id, school_id, email, password, student["full_name"])
    flash(err or "Student login enabled.", "error" if err else "success")
    return redirect(url_for("students.view_student", student_id=student_id))


@student_bp.route("/<student_id>/reset-password", methods=["POST"])
@school_admin_required
def reset_password(student_id):
    school_id = session["school_id"]
    pwd = request.form.get("new_password", "")
    if len(pwd) < 6:
        flash("Password must be at least 6 characters.", "error")
    else:
        ok, err = reset_student_password(student_id, school_id, pwd)
        flash(err or "Password reset.", "error" if err else "success")
    return redirect(url_for("students.view_student", student_id=student_id))
