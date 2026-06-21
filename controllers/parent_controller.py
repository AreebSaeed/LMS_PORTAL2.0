from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort,
)
from controllers.auth_helpers import school_admin_required
from models.school_model import get_school_by_id
from models.student_model import search_students
from models.parent_model import (
    RELATIONS,
    search_parents, get_parent_by_id, get_linked_students,
    get_notifications, get_linked_student_ids,
    create_parent, update_parent, deactivate_parent, delete_parent,
    enable_parent_login, reset_parent_password, send_notification,
)

parent_bp = Blueprint("parents", __name__)


def _admin_context(active_nav: str):
    school_id = session["school_id"]
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "full_name": session.get("full_name"),
        "role_label": "Admin",
        "active_nav": active_nav,
        "relations": RELATIONS,
    }


def _form_data(form):
    return {
        "full_name": form.get("full_name", ""),
        "relation": form.get("relation", "guardian"),
        "cnic": form.get("cnic", ""),
        "phone": form.get("phone", ""),
        "whatsapp": form.get("whatsapp", ""),
        "email": form.get("email", ""),
        "address": form.get("address", ""),
        "occupation": form.get("occupation", ""),
        "is_active": form.get("is_active") == "on",
    }


def _parse_student_ids(form):
    return form.getlist("student_ids")


@parent_bp.route("/")
@school_admin_required
def list_parents():
    school_id = session["school_id"]
    query = request.args.get("q", "").strip()
    parents = search_parents(school_id, query=query or None)

    for p in parents:
        p["children_count"] = len(get_linked_student_ids(p["id"]))

    ctx = _admin_context("parents")
    ctx.update({
        "parents": parents,
        "query": query,
        "page_title": "Parent Management",
    })
    return render_template("parents/list.html", **ctx)


@parent_bp.route("/add", methods=["GET", "POST"])
@school_admin_required
def add_parent():
    school_id = session["school_id"]
    all_students = search_students(school_id)

    if request.method == "POST":
        data = _form_data(request.form)
        student_ids = _parse_student_ids(request.form)

        if not data["full_name"]:
            flash("Parent name is required.", "error")
        else:
            try:
                parent = create_parent(school_id, data, student_ids)

                if request.form.get("enable_login") == "on":
                    email = data.get("email") or request.form.get("login_email", "")
                    password = request.form.get("login_password", "")
                    if email and password:
                        _, err = enable_parent_login(
                            parent["id"], school_id, email, password, data["full_name"]
                        )
                        if err:
                            flash(f"Parent saved, but login setup failed: {err}", "error")
                        else:
                            flash("Parent added with login access enabled.", "success")
                            return redirect(url_for("parents.view_parent", parent_id=parent["id"]))
                    else:
                        flash("Parent saved. Email and password required to enable login.", "error")

                flash(f"Parent {data['full_name']} added successfully.", "success")
                return redirect(url_for("parents.view_parent", parent_id=parent["id"]))
            except Exception:
                flash("Could not add parent record.", "error")

    ctx = _admin_context("parents")
    ctx.update({
        "parent": None,
        "all_students": all_students,
        "linked_ids": [],
        "page_title": "Add Parent / Guardian",
        "form_action": url_for("parents.add_parent"),
    })
    return render_template("parents/form.html", **ctx)


@parent_bp.route("/<parent_id>")
@school_admin_required
def view_parent(parent_id):
    school_id = session["school_id"]
    parent = get_parent_by_id(parent_id, school_id)
    if not parent:
        abort(404)

    ctx = _admin_context("parents")
    ctx.update({
        "parent": parent,
        "linked_students": get_linked_students(parent_id),
        "notifications": get_notifications(parent_id),
        "page_title": parent["full_name"],
    })
    return render_template("parents/detail.html", **ctx)


@parent_bp.route("/<parent_id>/edit", methods=["GET", "POST"])
@school_admin_required
def edit_parent(parent_id):
    school_id = session["school_id"]
    parent = get_parent_by_id(parent_id, school_id)
    if not parent:
        abort(404)

    all_students = search_students(school_id)
    linked_ids = get_linked_student_ids(parent_id)

    if request.method == "POST":
        data = _form_data(request.form)
        student_ids = _parse_student_ids(request.form)

        if not data["full_name"]:
            flash("Parent name is required.", "error")
        else:
            try:
                updated = update_parent(parent_id, school_id, data, student_ids)
                if updated:
                    flash("Parent updated successfully.", "success")
                    return redirect(url_for("parents.view_parent", parent_id=parent_id))
            except Exception:
                flash("Could not update parent.", "error")
        parent = get_parent_by_id(parent_id, school_id)
        linked_ids = get_linked_student_ids(parent_id)

    ctx = _admin_context("parents")
    ctx.update({
        "parent": parent,
        "all_students": all_students,
        "linked_ids": linked_ids,
        "page_title": f"Edit — {parent['full_name']}",
        "form_action": url_for("parents.edit_parent", parent_id=parent_id),
    })
    return render_template("parents/form.html", **ctx)


@parent_bp.route("/<parent_id>/enable-login", methods=["POST"])
@school_admin_required
def enable_login(parent_id):
    school_id = session["school_id"]
    parent = get_parent_by_id(parent_id, school_id)
    if not parent:
        abort(404)

    email = request.form.get("email", "").strip() or (parent.get("email") or "")
    password = request.form.get("password", "")

    if not password:
        flash("Password is required.", "error")
    else:
        _, err = enable_parent_login(parent_id, school_id, email, password, parent["full_name"])
        if err:
            flash(err, "error")
        else:
            flash("Parent login access enabled.", "success")

    return redirect(url_for("parents.view_parent", parent_id=parent_id))


@parent_bp.route("/<parent_id>/reset-password", methods=["POST"])
@school_admin_required
def reset_password(parent_id):
    school_id = session["school_id"]
    new_password = request.form.get("new_password", "")

    if len(new_password) < 6:
        flash("Password must be at least 6 characters.", "error")
    else:
        ok, err = reset_parent_password(parent_id, school_id, new_password)
        if ok:
            flash("Password reset successfully.", "success")
        else:
            flash(err or "Reset failed.", "error")

    return redirect(url_for("parents.view_parent", parent_id=parent_id))


@parent_bp.route("/<parent_id>/notify", methods=["POST"])
@school_admin_required
def notify_parent(parent_id):
    school_id = session["school_id"]
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()

    if not subject or not message:
        flash("Subject and message are required.", "error")
    else:
        result = send_notification(
            parent_id, school_id, subject, message,
            sent_by=session.get("user_id"),
        )
        if result:
            flash("Notification sent and logged.", "success")
        else:
            flash("Could not send notification.", "error")

    return redirect(url_for("parents.view_parent", parent_id=parent_id))


@parent_bp.route("/<parent_id>/delete", methods=["POST"])
@school_admin_required
def remove_parent(parent_id):
    school_id = session["school_id"]
    action = request.form.get("action", "deactivate")

    if action == "delete":
        if delete_parent(parent_id, school_id):
            flash("Parent record deleted.", "success")
            return redirect(url_for("parents.list_parents"))
        flash("Could not delete parent.", "error")
    else:
        if deactivate_parent(parent_id, school_id):
            flash("Parent deactivated.", "success")
        else:
            flash("Could not deactivate parent.", "error")

    return redirect(url_for("parents.view_parent", parent_id=parent_id))
