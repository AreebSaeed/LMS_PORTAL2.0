from models.timetable.repository import (
    delete_slot_by_id,
    delete_slots_by_ids,
    enrich_conflict_slot,
    find_overlapping_slots,
    find_teacher_overlapping_slots,
    insert_slot,
    update_slot_by_id,
)


def _validate_slot_assignment(school_id: str, data: dict, exclude_slot_id: str = None):
    teacher_id = data.get("teacher_id")
    class_id = data.get("class_id")
    day_of_week = (data.get("day_of_week") or "").lower()
    start_time = data.get("start_time")
    end_time = data.get("end_time")

    if not teacher_id or not class_id:
        return "Teacher and class are required.", None, None

    teacher_conflicts = find_teacher_overlapping_slots(
        school_id, teacher_id, day_of_week, start_time, end_time, exclude_slot_id
    )
    if teacher_conflicts:
        return "teacher_conflict", enrich_conflict_slot(teacher_conflicts[0], school_id), None

    class_conflicts = find_overlapping_slots(
        school_id, class_id, day_of_week, start_time, end_time, exclude_slot_id
    )
    if class_conflicts and not data.get("allow_replace"):
        return "conflict", enrich_conflict_slot(class_conflicts[0], school_id), class_conflicts

    return None, None, class_conflicts


def admin_add_slot(school_id: str, data: dict):
    teacher_id = data.get("teacher_id")
    err, conflict, class_conflicts = _validate_slot_assignment(school_id, data)
    if err:
        return None, err, conflict

    if class_conflicts:
        delete_slots_by_ids(school_id, [row["id"] for row in class_conflicts])

    slot = insert_slot(teacher_id, school_id, data)
    if slot:
        return slot, None, None
    return None, "Could not add slot.", None


def admin_add_slots_bulk(school_id: str, data: dict) -> dict:
    """Create multiple slots with the same teacher, class, subject, and room."""
    teacher_id = data.get("teacher_id")
    class_id = data.get("class_id")
    subject_id = data.get("subject_id")
    room = (data.get("room") or "").strip() or None
    slot_list = data.get("slots") or []

    if not teacher_id or not class_id or not subject_id:
        return {
            "created": [],
            "failed": [{"error": "missing_fields", "message": "Teacher, class, and subject are required."}],
        }
    if not slot_list:
        return {
            "created": [],
            "failed": [{"error": "no_slots", "message": "Select at least one time slot."}],
        }

    created = []
    failed = []
    for item in slot_list:
        day = (item.get("day_of_week") or "").lower()
        start = item.get("start_time")
        end = item.get("end_time")
        if not day or not start or not end:
            failed.append({**item, "error": "invalid_slot", "message": "Invalid day or time."})
            continue

        slot_data = {
            "teacher_id": teacher_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "room": room,
            "day_of_week": day,
            "start_time": start,
            "end_time": end,
        }
        slot, err, conflict = admin_add_slot(school_id, slot_data)
        if slot:
            created.append(slot)
            continue

        msg = "Could not add slot."
        if err == "teacher_conflict" and conflict:
            c = conflict
            cls = c.get("class_label") or "another class"
            day_l = (c.get("day_of_week") or day).title()
            st = str(c.get("start_time", start))[:5]
            et = str(c.get("end_time", end))[:5]
            msg = f"Teacher busy on {day_l} {st}–{et} ({cls})."
        elif err == "conflict":
            msg = "Class already has a slot at this time."

        failed.append({
            "day_of_week": day,
            "start_time": start,
            "end_time": end,
            "error": err or "failed",
            "message": msg,
        })

    return {"created": created, "failed": failed}


def admin_update_slot(slot_id: str, school_id: str, data: dict):
    payload = {
        "teacher_id": data.get("teacher_id"),
        "class_id": data.get("class_id") or None,
        "subject_id": data.get("subject_id") or None,
        "day_of_week": data["day_of_week"].lower(),
        "start_time": data["start_time"],
        "end_time": data["end_time"],
        "room": (data.get("room") or "").strip() or None,
    }

    err, conflict, class_conflicts = _validate_slot_assignment(
        school_id, {**data, **payload}, exclude_slot_id=slot_id
    )
    if err:
        return None, err, conflict

    if class_conflicts:
        delete_slots_by_ids(school_id, [row["id"] for row in class_conflicts])

    slot = update_slot_by_id(slot_id, school_id, payload)
    if slot:
        return slot, None, None
    return None, "Slot not found.", None


def admin_delete_slot(slot_id: str, school_id: str):
    if delete_slot_by_id(slot_id, school_id):
        return True, None
    return False, "Slot not found."
