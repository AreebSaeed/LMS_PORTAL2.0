from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort, Response,
)
from controllers.auth_helpers import staff_exam_required
from models.school_model import get_school_by_id
from models.teacher_model import get_teacher_by_user_id, get_subjects, get_classes, get_assigned_classes
from models.student_model import get_student_by_id
from models.exam_model import (
    EXAM_TERM_TYPES,
    list_exam_terms,
    get_exam_term,
    create_exam_term,
    get_exam_papers,
    add_exam_paper,
    delete_exam_paper,
    get_marks_matrix,
    save_subject_marks,
    calculate_term_results,
    get_term_results,
    get_student_term_result,
    get_student_subject_marks,
    publish_term_results,
    share_results_with_parents,
    get_student_result_history,
    teacher_can_access_term,
    generate_result_pdf,
)

exam_bp = Blueprint("exams", __name__)


def _load_teacher_id():
    if session.get("role") != "teacher":
        return None
    teacher = get_teacher_by_user_id(session["user_id"], session["school_id"])
    return teacher["id"] if teacher else None


def _ctx(active_nav: str, use_admin_sidebar: bool = True):
    school_id = session["school_id"]
    role = session.get("role")
    teacher_id = _load_teacher_id()
    classes = get_assigned_classes(teacher_id) if teacher_id else get_classes(school_id)
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "full_name": session.get("full_name"),
        "role": role,
        "active_nav": active_nav,
        "use_admin_sidebar": use_admin_sidebar and role == "school_admin",
        "classes": classes,
        "subjects": get_subjects(school_id),
        "term_types": EXAM_TERM_TYPES,
    }


def _check_term_access(term):
    if session.get("role") == "school_admin":
        return True
    teacher_id = _load_teacher_id()
    if not teacher_id:
        return False
    return teacher_can_access_term(teacher_id, term)


@exam_bp.route("/")
@staff_exam_required
def index():
    school_id = session["school_id"]
    class_id = request.args.get("class_id") or None
    teacher_id = _load_teacher_id()
    terms = list_exam_terms(school_id, class_id)
    if teacher_id:
        allowed = {c["id"] for c in get_assigned_classes(teacher_id)}
        terms = [t for t in terms if not t.get("class_id") or t["class_id"] in allowed]

    ctx = _ctx("exams")
    ctx.update({"terms": terms, "filter_class": class_id, "page_title": "Exam & Results"})
    template = "exams/list_admin.html" if session.get("role") == "school_admin" else "exams/list_teacher.html"
    return render_template(template, **ctx)


@exam_bp.route("/terms/add", methods=["GET", "POST"])
@staff_exam_required
def add_term():
    if session.get("role") != "school_admin":
        flash("Only admin can create exam terms.", "error")
        return redirect(url_for("exams.index"))

    school_id = session["school_id"]
    if request.method == "POST":
        data = {
            "name": request.form.get("name", ""),
            "term_type": request.form.get("term_type", "monthly_test"),
            "academic_year": request.form.get("academic_year", ""),
            "class_id": request.form.get("class_id") or None,
            "start_date": request.form.get("start_date") or None,
            "end_date": request.form.get("end_date") or None,
        }
        if not data["name"].strip():
            flash("Exam term name is required.", "error")
        elif not data["class_id"]:
            flash("Select a class.", "error")
        else:
            term = create_exam_term(school_id, data, session.get("user_id"))
            if term:
                flash("Exam term created.", "success")
                return redirect(url_for("exams.view_term", term_id=term["id"]))
            flash("Could not create exam term.", "error")

    ctx = _ctx("exams")
    ctx.update({"page_title": "Create Exam Term", "term": None})
    return render_template("exams/term_form.html", **ctx)


@exam_bp.route("/terms/<term_id>")
@staff_exam_required
def view_term(term_id):
    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or not _check_term_access(term):
        abort(403 if term else 404)

    papers = get_exam_papers(term_id, school_id)
    results = get_term_results(term_id, school_id)
    ctx = _ctx("exams")
    ctx.update({
        "term": term,
        "papers": papers,
        "results_count": len(results),
        "page_title": term["name"],
    })
    return render_template("exams/term_detail.html", **ctx)


@exam_bp.route("/terms/<term_id>/papers", methods=["POST"])
@staff_exam_required
def add_paper(term_id):
    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or not _check_term_access(term):
        abort(403 if term else 404)

    data = {
        "subject_id": request.form.get("subject_id"),
        "max_marks": request.form.get("max_marks", 100),
        "pass_marks": request.form.get("pass_marks", 33),
        "weight_percent": request.form.get("weight_percent", 100),
        "exam_date": request.form.get("exam_date") or None,
    }
    if not data["subject_id"]:
        flash("Select a subject.", "error")
    elif add_exam_paper(term_id, school_id, data):
        flash("Subject added to exam.", "success")
    else:
        flash("Could not add subject (may already exist).", "error")
    return redirect(url_for("exams.view_term", term_id=term_id))


@exam_bp.route("/papers/<paper_id>/delete", methods=["POST"])
@staff_exam_required
def remove_paper(paper_id):
    school_id = session["school_id"]
    term_id = request.form.get("term_id")
    if delete_exam_paper(paper_id, school_id):
        flash("Subject removed.", "success")
    else:
        flash("Could not remove subject.", "error")
    return redirect(url_for("exams.view_term", term_id=term_id))


@exam_bp.route("/terms/<term_id>/marks", methods=["GET", "POST"])
@staff_exam_required
def enter_marks(term_id):
    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or not _check_term_access(term):
        abort(403 if term else 404)

    class_id = term.get("class_id")
    papers, students, matrix = get_marks_matrix(term_id, school_id, class_id)

    if request.method == "POST":
        paper_id = request.form.get("paper_id")
        if not paper_id:
            flash("Invalid subject.", "error")
        else:
            marks = {sid: request.form.get(f"marks_{sid}", "") for sid in [s["id"] for s in students]}
            count = save_subject_marks(term_id, school_id, paper_id, marks, session.get("user_id"))
            flash(f"Saved marks for {count} student(s).", "success")
        return redirect(url_for("exams.enter_marks", term_id=term_id, paper_id=request.form.get("paper_id")))

    selected_paper = request.args.get("paper_id") or (papers[0]["id"] if papers else None)
    ctx = _ctx("exams")
    ctx.update({
        "term": term,
        "papers": papers,
        "students": students,
        "matrix": matrix,
        "selected_paper": selected_paper,
        "page_title": f"Enter Marks — {term['name']}",
    })
    return render_template("exams/enter_marks.html", **ctx)


@exam_bp.route("/terms/<term_id>/calculate", methods=["POST"])
@staff_exam_required
def calculate(term_id):
    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or not _check_term_access(term):
        abort(403 if term else 404)

    count = calculate_term_results(term_id, school_id, term.get("class_id"))
    flash(f"Calculated results for {count} student(s) with ranks.", "success")
    return redirect(url_for("exams.view_term", term_id=term_id))


@exam_bp.route("/terms/<term_id>/report")
@staff_exam_required
def class_report(term_id):
    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or not _check_term_access(term):
        abort(403 if term else 404)

    ctx = _ctx("exams")
    ctx.update({
        "term": term,
        "results": get_term_results(term_id, school_id),
        "papers": get_exam_papers(term_id, school_id),
        "page_title": f"Class Report — {term['name']}",
    })
    return render_template("exams/class_report.html", **ctx)


@exam_bp.route("/terms/<term_id>/student/<student_id>")
@staff_exam_required
def result_card(term_id, student_id):
    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or not _check_term_access(term):
        abort(403 if term else 404)

    student = get_student_by_id(student_id, school_id)
    result = get_student_term_result(term_id, student_id, school_id)
    if not student:
        abort(404)

    ctx = _ctx("exams")
    ctx.update({
        "term": term,
        "student": student,
        "result": result,
        "subject_marks": get_student_subject_marks(term_id, student_id, school_id),
        "page_title": f"Result Card — {student['full_name']}",
    })
    return render_template("exams/result_card.html", **ctx)


@exam_bp.route("/terms/<term_id>/student/<student_id>/pdf")
@staff_exam_required
def result_pdf(term_id, student_id):
    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or not _check_term_access(term):
        abort(403 if term else 404)

    student = get_student_by_id(student_id, school_id)
    result = get_student_term_result(term_id, student_id, school_id)
    if not student or not result:
        abort(404)

    school = get_school_by_id(school_id)
    subject_marks = get_student_subject_marks(term_id, student_id, school_id)
    pdf_bytes = generate_result_pdf(school, term, student, result, subject_marks)
    filename = f"result_{student.get('admission_number', student_id[:8])}_{term['name'][:20]}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@exam_bp.route("/terms/<term_id>/publish", methods=["POST"])
@staff_exam_required
def publish(term_id):
    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or session.get("role") != "school_admin":
        abort(403 if term else 404)

    if publish_term_results(term_id, school_id):
        flash("Results published. Students and parents can now view them.", "success")
    else:
        flash("Publish failed.", "error")
    return redirect(url_for("exams.view_term", term_id=term_id))


@exam_bp.route("/terms/<term_id>/share-parents", methods=["POST"])
@staff_exam_required
def share_parents(term_id):
    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or session.get("role") != "school_admin":
        abort(403 if term else 404)

    count, err = share_results_with_parents(term_id, school_id, session.get("user_id"))
    if err:
        flash(err, "error")
    else:
        flash(f"Shared results with {count} parent notification(s).", "success")
    return redirect(url_for("exams.view_term", term_id=term_id))


@exam_bp.route("/student/<student_id>/history")
@staff_exam_required
def student_history(student_id):
    school_id = session["school_id"]
    student = get_student_by_id(student_id, school_id)
    if not student:
        abort(404)

    ctx = _ctx("exams")
    ctx.update({
        "student": student,
        "history": get_student_result_history(student_id, school_id, published_only=False),
        "page_title": f"Result History — {student['full_name']}",
    })
    return render_template("exams/student_history.html", **ctx)
