from functools import wraps
from flask import session, redirect, url_for, flash


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def school_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") != "school_admin":
            flash("Access denied. Admin privileges required.", "error")
            return redirect(url_for("dashboard.index"))
        if not session.get("school_id"):
            flash("No school assigned to your account.", "error")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated


def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") != "teacher":
            flash("Access denied. Teacher privileges required.", "error")
            return redirect(url_for("dashboard.index"))
        if not session.get("school_id"):
            flash("No school assigned to your account.", "error")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated


def parent_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") != "parent":
            flash("Access denied. Parent privileges required.", "error")
            return redirect(url_for("dashboard.index"))
        if not session.get("school_id"):
            flash("No school assigned to your account.", "error")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") != "student":
            flash("Access denied. Student privileges required.", "error")
            return redirect(url_for("dashboard.index"))
        if not session.get("school_id"):
            flash("No school assigned to your account.", "error")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated


def staff_exam_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") not in ("school_admin", "teacher"):
            flash("Access denied.", "error")
            return redirect(url_for("dashboard.index"))
        if not session.get("school_id"):
            flash("No school assigned to your account.", "error")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated


def fee_staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") not in ("school_admin", "accountant"):
            flash("Access denied. Admin or accountant privileges required.", "error")
            return redirect(url_for("dashboard.index"))
        if not session.get("school_id"):
            flash("No school assigned to your account.", "error")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated
