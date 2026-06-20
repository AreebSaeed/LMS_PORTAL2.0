from functools import wraps
from flask import Blueprint, render_template, session, redirect, url_for
from models.school_model import get_all_schools, get_school_by_id, get_school_stats

dashboard_bp = Blueprint("dashboard", __name__)

ROLE_TEMPLATE_MAP = {
    "super_admin":  "dashboards/super_admin.html",
    "school_admin": "dashboards/school_admin.html",
    "accountant":   "dashboards/accountant.html",
    "teacher":      "dashboards/teacher.html",
    "student":      "dashboards/student.html",
    "parent":       "dashboards/parent.html",
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

    context = {
        "full_name": session.get("full_name"),
        "role": role,
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
        school = get_school_by_id(session["school_id"])
        stats = get_school_stats(session["school_id"])
        context["school"] = school
        context.update(stats)

    return render_template(template, **context)
