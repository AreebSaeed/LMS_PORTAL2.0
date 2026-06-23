from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify,
)
from controllers.auth_helpers import school_admin_required, portal_session_required
from models.school_model import get_school_by_id
from models.admin_model import (
    get_school_announcements,
    create_school_announcement,
    delete_school_announcement,
)
from models.announcement_model import (
    parse_audience_from_form,
    audience_summary,
    format_audience_label,
    get_unread_announcements,
    mark_announcement_read,
    mark_all_announcements_read,
    announcements_list_url_for_role,
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
        audience = parse_audience_from_form(request.form)
        if not title:
            flash("Title is required.", "error")
        elif not body:
            flash("Message is required.", "error")
        elif not audience:
            flash("Select at least one audience: teachers, students, or parents.", "error")
        else:
            teachers, students, parents = audience
            if create_school_announcement(
                school_id,
                session["user_id"],
                title,
                body,
                audience_teachers=teachers,
                audience_students=students,
                audience_parents=parents,
            ):
                flash(
                    f"Announcement posted for {audience_summary(teachers, students, parents)}.",
                    "success",
                )
                return redirect(url_for("announcements.index"))
            flash("Could not post announcement.", "error")

    ctx = _admin_context("announcements")
    ctx.update({
        "announcements": get_school_announcements(school_id),
        "format_audience_label": format_audience_label,
        "page_title": "Announcements",
    })
    return render_template("announcements/index.html", **ctx)


@announcement_bp.route("/api/unread")
@portal_session_required
def api_unread():
    user_id = session["user_id"]
    school_id = session["school_id"]
    role = session.get("role", "")
    items = get_unread_announcements(user_id, school_id, role, limit=25)
    return jsonify({
        "count": len(items),
        "items": items,
        "list_url": announcements_list_url_for_role(role),
    })


@announcement_bp.route("/api/<announcement_type>/<announcement_id>/read", methods=["POST"])
@portal_session_required
def api_mark_read(announcement_type, announcement_id):
    ok = mark_announcement_read(session["user_id"], announcement_id, announcement_type)
    return jsonify({"ok": ok})


@announcement_bp.route("/api/read-all", methods=["POST"])
@portal_session_required
def api_read_all():
    user_id = session["user_id"]
    school_id = session["school_id"]
    role = session.get("role", "")
    items = get_unread_announcements(user_id, school_id, role, limit=100)
    mark_all_announcements_read(user_id, items)
    return jsonify({"ok": True, "count": len(items)})


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
