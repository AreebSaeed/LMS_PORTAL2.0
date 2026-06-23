from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify,
)
from controllers.auth_helpers import school_admin_required
from models.school_model import get_school_by_id
from models.timetable_model import (
    build_time_ranges,
    fetch_school_timetable,
    admin_add_slot,
    admin_update_slot,
    admin_delete_slot,
    teachers_for_select,
    classes_for_select,
    subjects_for_select,
    HOURLY_START_OPTIONS,
    HOURLY_END_OPTIONS,
    _class_label,
)
from models.class_model import get_class_by_id

timetable_bp = Blueprint("timetable", __name__)


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
    class_opts = classes_for_select(school_id)

    if not class_id and class_opts:
        class_id = class_opts[0]["id"]

    slots = fetch_school_timetable(school_id, class_id) if class_id else []
    selected_class = get_class_by_id(class_id, school_id) if class_id else None

    ctx = _ctx("timetable")
    ctx.update({
        "page_title": "Class Timetable",
        "tt_slots": slots,
        "tt_time_ranges": build_time_ranges(),
        "tt_class_options": class_opts,
        "tt_subjects": subjects_for_select(school_id),
        "tt_teachers": teachers_for_select(school_id),
        "tt_can_edit": True,
        "tt_title": "Class Timetable",
        "tt_admin_mode": True,
        "selected_class_id": class_id,
        "selected_class_label": _class_label(selected_class) if selected_class else "",
        "hourly_starts": HOURLY_START_OPTIONS,
        "hourly_ends": HOURLY_END_OPTIONS,
        "tt_api_add": url_for("timetable.add_slot"),
        "tt_api_update": url_for("timetable.update_slot", slot_id="__ID__"),
        "tt_api_delete": url_for("timetable.delete_slot", slot_id="__ID__"),
    })
    return render_template("timetable/admin.html", **ctx)


@timetable_bp.route("/slots", methods=["POST"])
@school_admin_required
def add_slot():
    school_id = session["school_id"]
    data = request.get_json(silent=True) or request.form
    required = ["teacher_id", "class_id", "subject_id", "day_of_week", "start_time", "end_time"]
    if not all(data.get(k) for k in required):
        return jsonify({"success": False, "error": "All required fields must be filled."}), 400

    slot, err, conflict = admin_add_slot(school_id, data)
    if slot:
        flash("Timetable slot added. Students in this class will see it automatically.", "success")
        return jsonify({"success": True, "slot": slot})
    if err == "conflict":
        return jsonify({
            "success": False,
            "error": "Time slot already has an event for this class. Replace it?",
            "conflict": True,
            "conflict_slot": conflict,
        }), 409
    return jsonify({"success": False, "error": err or "Could not add slot."}), 500


@timetable_bp.route("/slots/<slot_id>", methods=["POST"])
@school_admin_required
def update_slot(slot_id):
    school_id = session["school_id"]
    data = request.get_json(silent=True) or request.form
    slot, err, conflict = admin_update_slot(slot_id, school_id, data)
    if slot:
        flash("Timetable slot updated.", "success")
        return jsonify({"success": True, "slot": slot})
    if err == "conflict":
        return jsonify({
            "success": False,
            "error": "Time slot already has an event for this class. Replace it?",
            "conflict": True,
            "conflict_slot": conflict,
        }), 409
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
