"""Timetable domain — slots, availability, and admin CRUD."""

from models.timetable.admin import (
    admin_add_slot,
    admin_add_slots_bulk,
    admin_delete_slot,
    admin_update_slot,
)
from models.timetable.availability import get_slot_availability
from models.timetable.constants import (
    DAY_LABELS,
    DAYS,
    HOURLY_END_OPTIONS,
    HOURLY_START_OPTIONS,
    PASTEL_COLORS,
    build_time_ranges,
)
from models.timetable.helpers import (
    class_filter_options,
    class_label,
    color_for_subject,
    normalize_class_slots,
    normalize_slot,
    normalize_teacher_slots,
    subject_legend,
)
from models.timetable.repository import (
    delete_slot_by_id,
    enrich_conflict_slot,
    fetch_class_timetable,
    fetch_school_timetable,
    get_teacher_slot,
    insert_slot,
    update_slot_by_id,
)
from models.timetable.selectors import (
    classes_for_select,
    subjects_for_select,
    teachers_for_select,
)

# Backward-compatible alias used by portal controllers
_class_label = class_label

# Legacy teacher-scoped CRUD names
add_timetable_slot = insert_slot
update_timetable_slot = update_slot_by_id
delete_timetable_slot = delete_slot_by_id

__all__ = [
    "DAYS",
    "DAY_LABELS",
    "PASTEL_COLORS",
    "HOURLY_START_OPTIONS",
    "HOURLY_END_OPTIONS",
    "build_time_ranges",
    "class_label",
    "_class_label",
    "color_for_subject",
    "normalize_slot",
    "normalize_teacher_slots",
    "normalize_class_slots",
    "class_filter_options",
    "subject_legend",
    "add_timetable_slot",
    "update_timetable_slot",
    "delete_timetable_slot",
    "get_teacher_slot",
    "fetch_class_timetable",
    "fetch_school_timetable",
    "get_slot_availability",
    "admin_add_slot",
    "admin_add_slots_bulk",
    "admin_update_slot",
    "admin_delete_slot",
    "teachers_for_select",
    "classes_for_select",
    "subjects_for_select",
]
