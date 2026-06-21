from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash,
)
from controllers.auth_helpers import school_admin_required
from models.school_model import get_school_by_id
from models.admin_model import (
    get_school_announcements,
    create_school_announcement,
    delete_school_announcement,
)

announcement_bp = Blueprint("announcements", __name__)


def _admin_context(active_nav: str):
    school_id = session["school_id"]
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "full_name": session.get("full_name"),
        "role_label": "Admin",
        "active_nav": active_nav,
    }


@announcement_bp.route("/", methods=["GET", "POST"])
@school_admin_required
def index():
    school_id = session["school_id"]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title:
            flash("Title is required.", "error")
        elif not body:
            flash("Message is required.", "error")
        elif create_school_announcement(
            school_id, session["user_id"], title, body
        ):
            flash("Announcement posted for teachers, students, and parents.", "success")
            return redirect(url_for("announcements.index"))
        else:
            flash("Could not post announcement.", "error")

    ctx = _admin_context("announcements")
    ctx.update({
        "announcements": get_school_announcements(school_id),
        "page_title": "Announcements",
    })
    return render_template("announcements/index.html", **ctx)


@announcement_bp.route("/<announcement_id>/delete", methods=["POST"])
@school_admin_required
def delete(announcement_id):
    school_id = session["school_id"]
    if request.form.get("action") == "delete":
        if delete_school_announcement(school_id, announcement_id):
            flash("Announcement deleted.", "success")
        else:
            flash("Could not delete announcement.", "error")
    return redirect(url_for("announcements.index"))
