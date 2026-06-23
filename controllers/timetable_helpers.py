from flask import jsonify

from models.timetable.constants import HOURLY_END_OPTIONS, HOURLY_START_OPTIONS, build_time_ranges
from models.timetable.helpers import class_label
from models.timetable.selectors import classes_for_select, subjects_for_select, teachers_for_select


def conflict_json(err: str, conflict: dict):
    if err == "conflict":
        return jsonify({
            "success": False,
            "error": "Time slot already has an event for this class. Replace it?",
            "conflict": True,
            "conflict_type": "class",
            "conflict_slot": conflict,
        }), 409

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


def admin_page_context(school_id: str, class_id: str, urls: dict) -> dict:
    from models.class_model import get_class_by_id
    from models.timetable.repository import fetch_school_timetable

    class_opts = classes_for_select(school_id)
    if not class_id and class_opts:
        class_id = class_opts[0]["id"]

    slots = fetch_school_timetable(school_id, class_id) if class_id else []
    selected_class = get_class_by_id(class_id, school_id) if class_id else None

    return {
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
        "selected_class_label": class_label(selected_class) if selected_class else "",
        "hourly_starts": HOURLY_START_OPTIONS,
        "hourly_ends": HOURLY_END_OPTIONS,
        "tt_api_add": urls["add"],
        "tt_api_add_bulk": urls["add_bulk"],
        "tt_api_update": urls["update"],
        "tt_api_delete": urls["delete"],
        "tt_api_availability": urls["availability"],
    }
