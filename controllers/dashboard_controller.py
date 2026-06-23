from functools import wraps
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from controllers.auth_helpers import school_admin_required
from models.school_model import get_all_schools, get_school_by_id, get_school_stats
from models.admin_model import get_admin_dashboard_data
from models.admission_model import (
    ADMISSION_STATUSES,
    list_admissions,
    create_admission,
    update_admission_status,
)

dashboard_bp = Blueprint("dashboard", __name__)

ROLE_LABELS = {
    "super_admin": "Super Admin",
    "school_admin": "Admin",
    "accountant": "Accountant",
    "teacher": "Teacher",
    "student": "Student",
    "parent": "Parent",
}

ROLE_DASHBOARD_TITLES = {
    "super_admin": "SaaS Control Panel",
    "school_admin": "Admin Dashboard",
    "accountant": "Fee Dashboard",
    "teacher": "Teacher Dashboard",
    "student": "Student Dashboard",
    "parent": "Parent Dashboard",
}

ROLE_TEMPLATE_MAP = {
    "super_admin": "dashboards/super_admin.html",
    "school_admin": "dashboards/school_admin.html",
    "accountant": "dashboards/accountant.html",
    "teacher": "dashboards/teacher.html",
    "student": "dashboards/student.html",
    "parent": "dashboards/parent.html",
}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@dashboard_bp.route("/")
@login_required
def index():
    role = session.get("role")
    template = ROLE_TEMPLATE_MAP.get(role)

    if not template:
        return "Unauthorized role.", 403

    if role == "parent":
        return redirect(url_for("parent_portal.dashboard"))

    if role == "teacher":
        return redirect(url_for("teacher_portal.dashboard"))

    if role == "student":
        return redirect(url_for("student_portal.dashboard"))

    if role == "accountant":
        return redirect(url_for("fees.index"))

    context = {
        "full_name": session.get("full_name"),
        "role": role,
        "role_label": ROLE_LABELS.get(role, role),
        "dashboard_title": ROLE_DASHBOARD_TITLES.get(role, "Dashboard"),
        "school_id": session.get("school_id"),
    }

    if role == "super_admin":
        schools = get_all_schools()
        context["schools"] = schools
        context["total_schools"] = len(schools)
        context["active_schools"] = sum(1 for s in schools if s["status"] == "active")
        context["disabled_schools"] = sum(1 for s in schools if s["status"] == "disabled")
        context["inactive_schools"] = sum(1 for s in schools if s["status"] == "inactive")

    elif session.get("school_id"):
        school_id = session["school_id"]
        school = get_school_by_id(school_id)

        if role == "school_admin":
            admin_data = get_admin_dashboard_data(school_id)
            context["school"] = school
            context.update(admin_data)
        else:
            stats = get_school_stats(school_id)
            context["school"] = school
            context.update(stats)

    return render_template(template, **context)


def _admin_page_context(active_nav: str):
    school_id = session["school_id"]
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "full_name": session.get("full_name"),
        "role_label": "Admin",
        "active_nav": active_nav,
    }


@dashboard_bp.route("/admissions", methods=["GET", "POST"])
@school_admin_required
def admissions():
    school_id = session["school_id"]

    if request.method == "POST":
        action = request.form.get("action", "create")
        if action == "create":
            name = request.form.get("student_name", "").strip()
            grade = request.form.get("grade", "").strip()
            if not name:
                flash("Student name is required.", "error")
            elif create_admission(school_id, name, grade):
                flash("Admission application recorded.", "success")
                return redirect(url_for("dashboard.admissions"))
            else:
                flash("Could not save admission.", "error")
        elif action in ADMISSION_STATUSES:
            admission_id = request.form.get("admission_id", "")
            if admission_id and update_admission_status(school_id, admission_id, action):
                flash(f"Application marked as {action}.", "success")
                return redirect(url_for("dashboard.admissions"))
            flash("Could not update application.", "error")

    ctx = _admin_page_context("admissions")
    admissions_list = list_admissions(school_id)
    ctx.update({
        "admissions": admissions_list,
        "pending_count": sum(1 for a in admissions_list if a.get("status") == "pending"),
        "statuses": ADMISSION_STATUSES,
        "page_title": "Admissions",
    })
    return render_template("admissions/index.html", **ctx)


@dashboard_bp.route("/reports")
@school_admin_required
def reports():
    ctx = _admin_page_context("reports")
    ctx["page_title"] = "Reports"
    return render_template("reports/index.html", **ctx)
