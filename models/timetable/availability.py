from models.supabase_client import supabase_admin
from models.timetable.constants import DAY_LABELS, DAYS, build_time_ranges
from models.timetable.helpers import class_label, slot_covers_range
from models.timetable.repository import fetch_raw_slots


def _resolve_cell_status(teacher_hit: dict, class_hit: dict) -> str:
    if teacher_hit and class_hit:
        if teacher_hit.get("id") == class_hit.get("id"):
            return "class_busy"
        return "both_busy"
    if class_hit:
        return "class_busy"
    if teacher_hit:
        return "teacher_busy"
    return "free"


def get_slot_availability(
    school_id: str,
    teacher_id: str,
    class_id: str,
    exclude_slot_id: str = None,
) -> dict:
    """Build a weekly grid showing teacher/class busy times and mutual free slots."""
    ranges = build_time_ranges()
    teacher_rows = [
        r for r in fetch_raw_slots(school_id, teacher_id=teacher_id)
        if not exclude_slot_id or r.get("id") != exclude_slot_id
    ]
    class_rows = [
        r for r in fetch_raw_slots(school_id, class_id=class_id)
        if not exclude_slot_id or r.get("id") != exclude_slot_id
    ]

    class_ids = {r["class_id"] for r in teacher_rows if r.get("class_id")}
    teacher_ids = {r["teacher_id"] for r in class_rows if r.get("teacher_id")}

    class_map = {}
    teacher_map = {}
    if class_ids:
        classes = (
            supabase_admin.table("classes")
            .select("id, name, grade, section")
            .in_("id", list(class_ids))
            .execute()
            .data or []
        )
        class_map = {c["id"]: c for c in classes}
    if teacher_ids:
        teachers = (
            supabase_admin.table("teachers")
            .select("id, full_name")
            .in_("id", list(teacher_ids))
            .execute()
            .data or []
        )
        teacher_map = {t["id"]: t["full_name"] for t in teachers}

    cells = []
    free_slots = []
    for day in DAYS:
        for r in ranges:
            rs, re = r["start"], r["end"]
            teacher_hit = next(
                (
                    row for row in teacher_rows
                    if row.get("day_of_week", "").lower() == day
                    and slot_covers_range(row, rs, re)
                ),
                None,
            )
            class_hit = next(
                (
                    row for row in class_rows
                    if row.get("day_of_week", "").lower() == day
                    and slot_covers_range(row, rs, re)
                ),
                None,
            )
            status = _resolve_cell_status(teacher_hit, class_hit)

            if status == "free":
                free_slots.append({
                    "day_of_week": day,
                    "day_label": DAY_LABELS[day],
                    "start_time": rs,
                    "end_time": re,
                    "label": f"{DAY_LABELS[day][:3]} {r['label']}",
                })

            teacher_label = ""
            if teacher_hit and teacher_hit.get("class_id"):
                teacher_label = class_label(class_map.get(teacher_hit["class_id"], {}))

            class_slot_teacher = ""
            if class_hit and class_hit.get("teacher_id"):
                class_slot_teacher = teacher_map.get(class_hit["teacher_id"], "")

            cells.append({
                "day_of_week": day,
                "day_label": DAY_LABELS[day],
                "start_time": rs,
                "end_time": re,
                "time_label": r["label"],
                "status": status,
                "teacher_class": teacher_label,
                "class_slot_teacher": class_slot_teacher,
            })

    return {
        "cells": cells,
        "free_slots": free_slots,
        "free_count": len(free_slots),
    }
