from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify,
)
from controllers.auth_helpers import school_admin_required
from controllers.timetable_helpers import admin_page_context, conflict_json
from models.school_model import get_school_by_id
from models.timetable import (
    admin_add_slot,
    admin_add_slots_bulk,
    admin_delete_slot,
    admin_update_slot,
    get_slot_availability,
)

timetable_bp = Blueprint("timetable", __name__)

SLOT_REQUIRED_FIELDS = ["teacher_id", "class_id", "subject_id", "day_of_week", "start_time", "end_time"]
BULK_REQUIRED_FIELDS = ["teacher_id", "class_id", "subject_id"]


def _ctx(active_nav: str):
    school_id = session["school_id"]
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "full_name": session.get("full_name"),
        "role_label": "Admin",
        "active_nav": active_nav,
        "use_admin_sidebar": True,
    }


@timetable_bp.route("/")
@school_admin_required
def index():
    school_id = session["school_id"]
    class_id = request.args.get("class_id") or None
    ctx = _ctx("timetable")
    ctx.update(admin_page_context(school_id, class_id, {
        "add": url_for("timetable.add_slot"),
        "add_bulk": url_for("timetable.add_slots_bulk"),
        "update": url_for("timetable.update_slot", slot_id="__ID__"),
        "delete": url_for("timetable.delete_slot", slot_id="__ID__"),
        "availability": url_for("timetable.slot_availability"),
    }))
    return render_template("timetable/admin.html", **ctx)


@timetable_bp.route("/slots", methods=["POST"])
@school_admin_required
def add_slot():
    school_id = session["school_id"]
    data = request.get_json(silent=True) or request.form
    if not all(data.get(k) for k in SLOT_REQUIRED_FIELDS):
        return jsonify({"success": False, "error": "All required fields must be filled."}), 400

    slot, err, conflict = admin_add_slot(school_id, data)
    if slot:
        flash("Timetable slot added. Students in this class will see it automatically.", "success")
        return jsonify({"success": True, "slot": slot})
    if err in ("conflict", "teacher_conflict"):
        return conflict_json(err, conflict)
    return jsonify({"success": False, "error": err or "Could not add slot."}), 500


@timetable_bp.route("/slots/bulk", methods=["POST"])
@school_admin_required
def add_slots_bulk():
    school_id = session["school_id"]
    data = request.get_json(silent=True) or {}
    if not all(data.get(k) for k in BULK_REQUIRED_FIELDS):
        return jsonify({"success": False, "error": "Teacher, class, and subject are required."}), 400

    result = admin_add_slots_bulk(school_id, data)
    created = result.get("created") or []
    failed = result.get("failed") or []

    if created:
        n = len(created)
        flash(
            f"Added {n} timetable slot{'s' if n != 1 else ''}. Students in this class will see them automatically.",
            "success",
        )

    if not created:
        msg = failed[0]["message"] if failed else "Could not add slots."
        return jsonify({"success": False, "error": msg, "failed": failed}), 400

    return jsonify({
        "success": True,
        "created_count": len(created),
        "failed_count": len(failed),
        "slots": created,
        "failed": failed,
    })


@timetable_bp.route("/availability")
@school_admin_required
def slot_availability():
    school_id = session["school_id"]
    teacher_id = request.args.get("teacher_id")
    class_id = request.args.get("class_id")
    exclude_slot_id = request.args.get("exclude_slot_id") or None
    if not teacher_id or not class_id:
        return jsonify({"success": False, "error": "teacher_id and class_id are required."}), 400
    data = get_slot_availability(school_id, teacher_id, class_id, exclude_slot_id)
    return jsonify({"success": True, **data})


@timetable_bp.route("/slots/<slot_id>", methods=["POST"])
@school_admin_required
def update_slot(slot_id):
    school_id = session["school_id"]
    data = request.get_json(silent=True) or request.form
    slot, err, conflict = admin_update_slot(slot_id, school_id, data)
    if slot:
        flash("Timetable slot updated.", "success")
        return jsonify({"success": True, "slot": slot})
    if err in ("conflict", "teacher_conflict"):
        return conflict_json(err, conflict)
    return jsonify({"success": False, "error": err or "Could not update slot."}), 500


@timetable_bp.route("/slots/<slot_id>/delete", methods=["POST"])
@school_admin_required
def delete_slot(slot_id):
    school_id = session["school_id"]
    ok, err = admin_delete_slot(slot_id, school_id)
    if ok:
        flash("Timetable slot removed.", "success")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": err or "Could not delete slot."}), 500
