from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort,
)
from controllers.auth_helpers import school_admin_required
from models.school_model import get_school_by_id
from models.student_message_model import (
    RECIPIENT_ADMIN,
    get_messages_for_admin,
    get_message_by_id,
    reply_to_message,
    mark_student_message_notifications_read,
    get_staff_message_notifications,
)

student_message_bp = Blueprint("student_messages", __name__)


def _admin_context(active_nav: str):
    school_id = session["school_id"]
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "full_name": session.get("full_name"),
        "role_label": "Admin",
        "active_nav": active_nav,
    }


@student_message_bp.route("/students", methods=["GET", "POST"])
@school_admin_required
def admin_inbox():
    school_id = session["school_id"]
    user_id = session["user_id"]

    if request.method == "POST":
        message_id = request.form.get("message_id", "").strip()
        reply_text = request.form.get("reply", "").strip()
        msg = get_message_by_id(message_id, school_id) if message_id else None
        if not msg:
            flash("Message not found.", "error")
        elif msg.get("recipient_type") not in (RECIPIENT_ADMIN, None):
            flash("This message is not addressed to admin.", "error")
        elif reply_to_message(message_id, school_id, reply_text, user_id):
            flash("Reply sent to student.", "success")
            return redirect(url_for("student_messages.admin_inbox"))
        else:
            flash("Could not send reply.", "error")

    mark_student_message_notifications_read(user_id, school_id)

    ctx = _admin_context("student_messages")
    ctx.update({
        "messages_list": get_messages_for_admin(school_id),
        "notifications": get_staff_message_notifications(user_id, school_id),
        "page_title": "Student Messages",
    })
    return render_template("messages/admin_student_inbox.html", **ctx)
