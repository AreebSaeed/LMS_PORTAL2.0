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
    admin_add_slots_bulk,
    admin_update_slot,
    admin_delete_slot,
    teachers_for_select,
    classes_for_select,
    subjects_for_select,
    get_slot_availability,
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
        "tt_api_add_bulk": url_for("timetable.add_slots_bulk"),
        "tt_api_update": url_for("timetable.update_slot", slot_id="__ID__"),
        "tt_api_delete": url_for("timetable.delete_slot", slot_id="__ID__"),
        "tt_api_availability": url_for("timetable.slot_availability"),
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
            "conflict_type": "class",
            "conflict_slot": conflict,
        }), 409
    if err == "teacher_conflict":
        c = conflict or {}
        cls = c.get("class_label") or "another class"
        day = (c.get("day_of_week") or "").title()
        st = str(c.get("start_time", ""))[:5]
        et = str(c.get("end_time", ""))[:5]
        return jsonify({
            "success": False,
            "error": (
                f"This teacher is already assigned on {day} {st}–{et} "
                f"({cls}). Choose a free slot below."
            ),
            "conflict": True,
            "conflict_type": "teacher",
            "conflict_slot": conflict,
        }), 409
    return jsonify({"success": False, "error": err or "Could not add slot."}), 500


@timetable_bp.route("/slots/bulk", methods=["POST"])
@school_admin_required
def add_slots_bulk():
    school_id = session["school_id"]
    data = request.get_json(silent=True) or {}
    required = ["teacher_id", "class_id", "subject_id"]
    if not all(data.get(k) for k in required):
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
    if err == "conflict":
        return jsonify({
            "success": False,
            "error": "Time slot already has an event for this class. Replace it?",
            "conflict": True,
            "conflict_type": "class",
            "conflict_slot": conflict,
        }), 409
    if err == "teacher_conflict":
        c = conflict or {}
        cls = c.get("class_label") or "another class"
        day = (c.get("day_of_week") or "").title()
        st = str(c.get("start_time", ""))[:5]
        et = str(c.get("end_time", ""))[:5]
        return jsonify({
            "success": False,
            "error": (
                f"This teacher is already assigned on {day} {st}–{et} "
                f"({cls}). Choose a free slot below."
            ),
            "conflict": True,
            "conflict_type": "teacher",
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
