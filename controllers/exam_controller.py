from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort, Response,
)
from controllers.auth_helpers import staff_exam_required
from models.school_model import get_school_by_id
from models.teacher_model import get_teacher_by_user_id, get_subjects, get_classes, get_assigned_classes
from models.student_model import get_student_by_id
from models.exam_model import (
    EXAM_ADMIN_TYPES,
    SUBMISSION_STATUSES,
    list_exam_terms,
    list_exam_groups,
    get_exam_group,
    get_terms_for_group,
    get_exam_history_years,
    get_exam_history_summary,
    get_group_history_detail,
    create_school_exam,
    get_exam_term,
    get_exam_papers,
    get_marks_matrix,
    save_subject_marks,
    calculate_term_results,
    get_term_results,
    get_student_term_result,
    get_student_subject_marks,
    submit_class_results,
    approve_class_results,
    reject_class_results,
    publish_exam_group,
    get_exam_group_analytics,
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
        "term_types": EXAM_ADMIN_TYPES,
        "submission_statuses": SUBMISSION_STATUSES,
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
    is_admin = session.get("role") == "school_admin"

    if is_admin:
        tab = request.args.get("tab", "active")
        if tab not in ("active", "history"):
            tab = "active"

        active_groups = list_exam_groups(school_id, published_only=False)
        history_summary = get_exam_history_summary(school_id)
        if tab == "history":
            history_groups = list_exam_groups(school_id, published_only=True, limit=50)
        else:
            history_groups = list_exam_groups(school_id, published_only=True, limit=5)

        ctx = _ctx("exams")
        ctx.update({
            "groups": active_groups,
            "history_groups": history_groups,
            "history_summary": history_summary,
            "active_tab": tab,
            "page_title": "Exam & Results",
        })
        return render_template("exams/list_admin.html", **ctx)

    class_id = request.args.get("class_id") or None
    teacher_id = _load_teacher_id()
    terms = list_exam_terms(school_id, class_id)
    if teacher_id:
        allowed = {c["id"] for c in get_assigned_classes(teacher_id)}
        terms = [t for t in terms if t.get("class_id") in allowed]

    ctx = _ctx("exams")
    ctx.update({"terms": terms, "filter_class": class_id, "page_title": "Exam & Results"})
    return render_template("exams/list_teacher.html", **ctx)


@exam_bp.route("/history")
@staff_exam_required
def history():
    if session.get("role") != "school_admin":
        abort(403)

    school_id = session["school_id"]
    academic_year = request.args.get("academic_year") or None
    term_type = request.args.get("term_type") or None

    history_groups = list_exam_groups(
        school_id,
        published_only=True,
        academic_year=academic_year,
        term_type=term_type if term_type in ("midterm", "final") else None,
        limit=200,
    )
    years = get_exam_history_years(school_id)
    summary = get_exam_history_summary(school_id)

    ctx = _ctx("exams")
    ctx.update({
        "history_groups": history_groups,
        "years": years,
        "summary": summary,
        "filter_year": academic_year,
        "filter_type": term_type,
        "page_title": "Exam & Results History",
    })
    return render_template("exams/history.html", **ctx)


@exam_bp.route("/groups/<group_id>/history")
@staff_exam_required
def group_history(group_id):
    if session.get("role") != "school_admin":
        abort(403)

    school_id = session["school_id"]
    detail = get_group_history_detail(group_id, school_id)
    if not detail:
        abort(404)

    ctx = _ctx("exams")
    ctx.update({
        "detail": detail,
        "group": detail["group"],
        "class_records": detail["class_records"],
        "page_title": f"History — {detail['group']['name']}",
    })
    return render_template("exams/group_history.html", **ctx)


@exam_bp.route("/add", methods=["GET", "POST"])
@exam_bp.route("/terms/add", methods=["GET", "POST"])
@staff_exam_required
def add_term():
    if session.get("role") != "school_admin":
        flash("Only admin can create exams.", "error")
        return redirect(url_for("exams.index"))

    school_id = session["school_id"]
    if request.method == "POST":
        data = {
            "name": request.form.get("name", ""),
            "term_type": request.form.get("term_type", "midterm"),
            "academic_year": request.form.get("academic_year", ""),
            "weight_percent": request.form.get("weight_percent", 100),
            "start_date": request.form.get("start_date") or None,
            "end_date": request.form.get("end_date") or None,
        }
        group, err = create_school_exam(school_id, data, session.get("user_id"))
        if group:
            flash(
                f"Exam created for all classes with subjects assigned automatically.",
                "success",
            )
            return redirect(url_for("exams.view_group", group_id=group["id"]))
        flash(err or "Could not create exam.", "error")

    ctx = _ctx("exams")
    ctx.update({"page_title": "Create Exam"})
    return render_template("exams/term_form.html", **ctx)


@exam_bp.route("/groups/<group_id>")
@staff_exam_required
def view_group(group_id):
    if session.get("role") != "school_admin":
        abort(403)

    school_id = session["school_id"]
    group = get_exam_group(group_id, school_id)
    if not group:
        abort(404)

    terms = get_terms_for_group(group_id, school_id)
    ctx = _ctx("exams")
    ctx.update({
        "group": group,
        "terms": terms,
        "page_title": group["name"],
    })
    return render_template("exams/group_detail.html", **ctx)


@exam_bp.route("/groups/<group_id>/analytics")
@staff_exam_required
def group_analytics(group_id):
    if session.get("role") != "school_admin":
        abort(403)

    school_id = session["school_id"]
    analytics = get_exam_group_analytics(group_id, school_id)
    if not analytics:
        abort(404)

    ctx = _ctx("exams")
    ctx.update({
        "analytics": analytics,
        "group": analytics["group"],
        "page_title": f"Analytics — {analytics['group']['name']}",
    })
    return render_template("exams/group_analytics.html", **ctx)


@exam_bp.route("/groups/<group_id>/publish", methods=["POST"])
@staff_exam_required
def publish_group(group_id):
    if session.get("role") != "school_admin":
        abort(403)

    school_id = session["school_id"]
    ok, err = publish_exam_group(group_id, school_id, session.get("user_id"))
    if ok:
        flash("Results published. Parents have been notified and can view results on their portal.", "success")
    else:
        flash(err or "Publish failed.", "error")
    return redirect(url_for("exams.view_group", group_id=group_id))


@exam_bp.route("/terms/<term_id>")
@staff_exam_required
def view_term(term_id):
    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or not _check_term_access(term):
        abort(403 if term else 404)

    is_admin = session.get("role") == "school_admin"
    if is_admin and term.get("exam_group_id"):
        return redirect(url_for("exams.view_group", group_id=term["exam_group_id"]))

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


@exam_bp.route("/terms/<term_id>/marks", methods=["GET", "POST"])
@staff_exam_required
def enter_marks(term_id):
    if session.get("role") == "school_admin":
        abort(403)

    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or not _check_term_access(term):
        abort(403 if term else 404)

    if term.get("submission_status") in ("submitted", "approved"):
        flash("Marks are locked while results await approval or are already approved.", "warning")
        return redirect(url_for("exams.view_term", term_id=term_id))

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


@exam_bp.route("/terms/<term_id>/submit", methods=["POST"])
@staff_exam_required
def submit_results(term_id):
    if session.get("role") == "school_admin":
        abort(403)

    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term or not _check_term_access(term):
        abort(403 if term else 404)

    ok, err = submit_class_results(term_id, school_id, session.get("user_id"))
    if ok:
        flash("Class results submitted to admin for approval.", "success")
    else:
        flash(err or "Submit failed.", "error")
    return redirect(url_for("exams.view_term", term_id=term_id))


@exam_bp.route("/terms/<term_id>/approve", methods=["POST"])
@staff_exam_required
def approve_results(term_id):
    if session.get("role") != "school_admin":
        abort(403)

    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term:
        abort(404)

    ok, err = approve_class_results(term_id, school_id)
    if ok:
        flash("Class results approved.", "success")
    else:
        flash(err or "Approval failed.", "error")

    group_id = term.get("exam_group_id")
    if group_id:
        return redirect(url_for("exams.view_group", group_id=group_id))
    return redirect(url_for("exams.view_term", term_id=term_id))


@exam_bp.route("/terms/<term_id>/reject", methods=["POST"])
@staff_exam_required
def reject_results(term_id):
    if session.get("role") != "school_admin":
        abort(403)

    school_id = session["school_id"]
    term = get_exam_term(term_id, school_id)
    if not term:
        abort(404)

    note = request.form.get("rejection_note", "")
    ok, err = reject_class_results(term_id, school_id, note)
    if ok:
        flash("Results sent back to teacher for correction.", "success")
    else:
        flash(err or "Rejection failed.", "error")

    group_id = term.get("exam_group_id")
    if group_id:
        return redirect(url_for("exams.view_group", group_id=group_id))
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
