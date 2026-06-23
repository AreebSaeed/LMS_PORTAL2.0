"""Normalize timetable data for the weekly UI and provide slot CRUD."""

import re

from models.supabase_client import supabase_admin

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
DAY_LABELS = {
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
    "saturday": "Saturday",
}

PASTEL_COLORS = [
    "#BFDBFE", "#BBF7D0", "#FDE68A", "#FBCFE8", "#DDD6FE",
    "#A5F3FC", "#FECACA", "#D9F99D", "#E9D5FF", "#FED7AA",
]

def _class_label(cls: dict) -> str:
    if not cls:
        return "—"
    name = cls.get("name") or cls.get("grade") or "Class"
    if cls.get("section"):
        return f"{name} — {cls['section']}"
    return name


def _time_str(val) -> str:
    if not val:
        return ""
    s = str(val).strip()
    m = re.match(r"(\d{1,2}):(\d{2})", s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return s[:5] if len(s) >= 5 else s


def _time_to_minutes(val) -> int:
    s = _time_str(val)
    if not s or ":" not in s:
        return 0
    h, m = s.split(":", 1)
    return int(h) * 60 + int(m)


def color_for_subject(subject_name: str) -> str:
    key = (subject_name or "default").strip().lower()
    idx = sum(ord(c) for c in key) % len(PASTEL_COLORS)
    return PASTEL_COLORS[idx]


def normalize_slot(row: dict, teacher_name: str = None) -> dict:
    cls = row.get("class_info") or {}
    sub = row.get("subject_info") or {}
    subject_name = row.get("subject_name") or sub.get("name") or "Subject"
    teacher = teacher_name or row.get("teacher_name") or "—"
    class_id = row.get("class_id") or cls.get("id")
    return {
        "id": row.get("id"),
        "subject_id": row.get("subject_id") or sub.get("id"),
        "subject_name": subject_name,
        "teacher_id": row.get("teacher_id"),
        "teacher_name": teacher,
        "class_id": class_id,
        "class_label": _class_label(cls) if cls else row.get("class_label", "—"),
        "room": row.get("room") or "",
        "day_of_week": (row.get("day_of_week") or "monday").lower(),
        "start_time": _time_str(row.get("start_time")),
        "end_time": _time_str(row.get("end_time")),
        "color": color_for_subject(subject_name),
    }


def normalize_teacher_slots(rows: list, teacher_name: str = None) -> list:
    out = []
    for row in rows or []:
        slot = normalize_slot(row, teacher_name=teacher_name)
        if row.get("class_info"):
            slot["class_label"] = _class_label(row["class_info"])
        if row.get("subject_info"):
            slot["subject_name"] = row["subject_info"].get("name", slot["subject_name"])
        out.append(slot)
    return _sort_slots(out)


def normalize_class_slots(rows: list) -> list:
    return _sort_slots([normalize_slot(r) for r in (rows or [])])


def _sort_slots(slots: list) -> list:
    return sorted(
        slots,
        key=lambda s: (
            DAYS.index(s["day_of_week"]) if s["day_of_week"] in DAYS else 99,
            s.get("start_time") or "",
        ),
    )


def build_time_ranges(slots: list = None) -> list:
    """Fixed 1-hour columns from 8 AM through 2 PM."""
    return [
        {"start": "08:00", "end": "09:00", "label": "8 AM – 9 AM"},
        {"start": "09:00", "end": "10:00", "label": "9 AM – 10 AM"},
        {"start": "10:00", "end": "11:00", "label": "10 AM – 11 AM"},
        {"start": "11:00", "end": "12:00", "label": "11 AM – 12 PM"},
        {"start": "12:00", "end": "13:00", "label": "12 PM – 1 PM"},
        {"start": "13:00", "end": "14:00", "label": "1 PM – 2 PM"},
    ]


HOURLY_START_OPTIONS = ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00"]
HOURLY_END_OPTIONS = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00"]


def class_filter_options(slots: list) -> list:
    opts = {}
    for s in slots:
        cid = s.get("class_id")
        if cid and cid not in opts:
            opts[cid] = {"id": cid, "label": s.get("class_label", "Class")}
    return sorted(opts.values(), key=lambda x: x["label"])


def subject_legend(slots: list) -> list:
    seen = {}
    for s in slots:
        name = s.get("subject_name", "Subject")
        if name not in seen:
            seen[name] = {"name": name, "color": s.get("color")}
    return list(seen.values())


def add_timetable_slot(teacher_id: str, school_id: str, data: dict):
    payload = {
        "teacher_id": teacher_id,
        "school_id": school_id,
        "class_id": data.get("class_id") or None,
        "subject_id": data.get("subject_id") or None,
        "day_of_week": data["day_of_week"].lower(),
        "start_time": data["start_time"],
        "end_time": data["end_time"],
        "room": (data.get("room") or "").strip() or None,
    }
    try:
        result = supabase_admin.table("teacher_timetable").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def update_timetable_slot(slot_id: str, teacher_id: str, school_id: str, data: dict):
    payload = {
        "class_id": data.get("class_id") or None,
        "subject_id": data.get("subject_id") or None,
        "day_of_week": data["day_of_week"].lower(),
        "start_time": data["start_time"],
        "end_time": data["end_time"],
        "room": (data.get("room") or "").strip() or None,
    }
    try:
        result = (
            supabase_admin.table("teacher_timetable")
            .update(payload)
            .eq("id", slot_id)
            .eq("teacher_id", teacher_id)
            .eq("school_id", school_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def delete_timetable_slot(slot_id: str, teacher_id: str, school_id: str) -> bool:
    try:
        result = (
            supabase_admin.table("teacher_timetable")
            .delete()
            .eq("id", slot_id)
            .eq("teacher_id", teacher_id)
            .eq("school_id", school_id)
            .execute()
        )
        return bool(result.data)
    except Exception:
        return False


def get_teacher_slot(slot_id: str, teacher_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("teacher_timetable")
            .select("*")
            .eq("id", slot_id)
            .eq("teacher_id", teacher_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def fetch_class_timetable(class_id: str, school_id: str) -> list:
    """Load timetable for a class — students/parents sync from this data."""
    if not class_id:
        return []
    from models.parent_portal_model import get_class_timetable

    rows = get_class_timetable(class_id, school_id)
    from models.class_model import get_class_by_id

    cls = get_class_by_id(class_id, school_id)
    for row in rows:
        if cls:
            row["class_info"] = cls
    return normalize_class_slots(rows)


def fetch_school_timetable(school_id: str, class_id: str = None) -> list:
    """All slots for admin view, optionally filtered by class."""
    try:
        q = (
            supabase_admin.table("teacher_timetable")
            .select("*")
            .eq("school_id", school_id)
            .order("day_of_week")
        )
        if class_id:
            q = q.eq("class_id", class_id)
        rows = q.execute().data or []
    except Exception:
        return []

    if not rows:
        return []

    class_ids = {r["class_id"] for r in rows if r.get("class_id")}
    subject_ids = {r["subject_id"] for r in rows if r.get("subject_id")}
    teacher_ids = {r["teacher_id"] for r in rows if r.get("teacher_id")}

    class_map, subject_map, teacher_map = {}, {}, {}
    if class_ids:
        classes = (
            supabase_admin.table("classes")
            .select("id, name, grade, section")
            .in_("id", list(class_ids))
            .execute()
            .data or []
        )
        class_map = {c["id"]: c for c in classes}
    if subject_ids:
        subjects = (
            supabase_admin.table("subjects")
            .select("id, name")
            .in_("id", list(subject_ids))
            .execute()
            .data or []
        )
        subject_map = {s["id"]: s for s in subjects}
    if teacher_ids:
        teachers = (
            supabase_admin.table("teachers")
            .select("id, full_name")
            .in_("id", list(teacher_ids))
            .execute()
            .data or []
        )
        teacher_map = {t["id"]: t["full_name"] for t in teachers}

    out = []
    for row in rows:
        row["class_info"] = class_map.get(row.get("class_id"))
        row["subject_info"] = subject_map.get(row.get("subject_id"))
        row["subject_name"] = (subject_map.get(row.get("subject_id")) or {}).get("name", "Subject")
        row["teacher_name"] = teacher_map.get(row.get("teacher_id"), "—")
        out.append(normalize_slot(row))
    return _sort_slots(out)


def _find_overlapping_slots(
    school_id: str,
    class_id: str,
    day_of_week: str,
    start_time: str,
    end_time: str,
    exclude_slot_id: str = None,
):
    """Return slots that overlap the given interval in the same class/day."""
    try:
        q = (
            supabase_admin.table("teacher_timetable")
            .select("*")
            .eq("school_id", school_id)
            .eq("class_id", class_id)
            .eq("day_of_week", day_of_week)
            .lt("start_time", end_time)
            .gt("end_time", start_time)
        )
        if exclude_slot_id:
            q = q.neq("id", exclude_slot_id)
        return q.execute().data or []
    except Exception:
        return []


def _find_teacher_overlapping_slots(
    school_id: str,
    teacher_id: str,
    day_of_week: str,
    start_time: str,
    end_time: str,
    exclude_slot_id: str = None,
):
    """Return slots where this teacher is already booked at the same time."""
    try:
        q = (
            supabase_admin.table("teacher_timetable")
            .select("*")
            .eq("school_id", school_id)
            .eq("teacher_id", teacher_id)
            .eq("day_of_week", day_of_week)
            .lt("start_time", end_time)
            .gt("end_time", start_time)
        )
        if exclude_slot_id:
            q = q.neq("id", exclude_slot_id)
        return q.execute().data or []
    except Exception:
        return []


def _times_overlap(slot_start: str, slot_end: str, range_start: str, range_end: str) -> bool:
    s0, s1 = _time_to_minutes(slot_start), _time_to_minutes(slot_end)
    r0, r1 = _time_to_minutes(range_start), _time_to_minutes(range_end)
    return s0 < r1 and s1 > r0


def _slot_covers_range(row: dict, range_start: str, range_end: str) -> bool:
    return _times_overlap(
        row.get("start_time"),
        row.get("end_time"),
        range_start,
        range_end,
    )


def _fetch_raw_slots(school_id: str, teacher_id: str = None, class_id: str = None) -> list:
    try:
        q = supabase_admin.table("teacher_timetable").select("*").eq("school_id", school_id)
        if teacher_id:
            q = q.eq("teacher_id", teacher_id)
        if class_id:
            q = q.eq("class_id", class_id)
        return q.execute().data or []
    except Exception:
        return []


def _enrich_conflict_slot(row: dict, school_id: str) -> dict:
    """Attach class label and subject name for conflict messages."""
    out = dict(row)
    if row.get("class_id"):
        from models.class_model import get_class_by_id

        cls = get_class_by_id(row["class_id"], school_id)
        if cls:
            out["class_label"] = _class_label(cls)
    if row.get("subject_id"):
        try:
            sub = (
                supabase_admin.table("subjects")
                .select("name")
                .eq("id", row["subject_id"])
                .single()
                .execute()
                .data
            )
            if sub:
                out["subject_name"] = sub.get("name")
        except Exception:
            pass
    out["start_time"] = _time_str(row.get("start_time"))
    out["end_time"] = _time_str(row.get("end_time"))
    return out


def get_slot_availability(
    school_id: str,
    teacher_id: str,
    class_id: str,
    exclude_slot_id: str = None,
) -> dict:
    """Build a weekly grid showing teacher/class busy times and mutual free slots."""
    ranges = build_time_ranges()
    teacher_rows = [
        r for r in _fetch_raw_slots(school_id, teacher_id=teacher_id)
        if not exclude_slot_id or r.get("id") != exclude_slot_id
    ]
    class_rows = [
        r for r in _fetch_raw_slots(school_id, class_id=class_id)
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
                    and _slot_covers_range(row, rs, re)
                ),
                None,
            )
            class_hit = next(
                (
                    row for row in class_rows
                    if row.get("day_of_week", "").lower() == day
                    and _slot_covers_range(row, rs, re)
                ),
                None,
            )
            if teacher_hit and class_hit:
                same_slot = teacher_hit.get("id") == class_hit.get("id")
                status = "class_busy" if same_slot else "both_busy"
            elif class_hit:
                status = "class_busy"
            elif teacher_hit:
                status = "teacher_busy"
            else:
                status = "free"
                free_slots.append({
                    "day_of_week": day,
                    "day_label": DAY_LABELS[day],
                    "start_time": rs,
                    "end_time": re,
                    "label": f"{DAY_LABELS[day][:3]} {r['label']}",
                })

            teacher_label = ""
            if teacher_hit and teacher_hit.get("class_id"):
                teacher_label = _class_label(class_map.get(teacher_hit["class_id"], {}))

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


def admin_add_slot(school_id: str, data: dict):
    teacher_id = data.get("teacher_id")
    class_id = data.get("class_id")
    day_of_week = (data.get("day_of_week") or "").lower()
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    allow_replace = bool(data.get("allow_replace"))
    if not teacher_id or not class_id:
        return None, "Teacher and class are required.", None

    teacher_conflicts = _find_teacher_overlapping_slots(
        school_id, teacher_id, day_of_week, start_time, end_time
    )
    if teacher_conflicts:
        return None, "teacher_conflict", _enrich_conflict_slot(teacher_conflicts[0], school_id)

    conflicts = _find_overlapping_slots(
        school_id, class_id, day_of_week, start_time, end_time
    )
    if conflicts and not allow_replace:
        return None, "conflict", _enrich_conflict_slot(conflicts[0], school_id)
    if conflicts and allow_replace:
        for row in conflicts:
            (
                supabase_admin.table("teacher_timetable")
                .delete()
                .eq("id", row["id"])
                .eq("school_id", school_id)
                .execute()
            )

    slot = add_timetable_slot(teacher_id, school_id, data)
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
        return {"created": [], "failed": [{"error": "missing_fields", "message": "Teacher, class, and subject are required."}]}
    if not slot_list:
        return {"created": [], "failed": [{"error": "no_slots", "message": "Select at least one time slot."}]}

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
    allow_replace = bool(data.get("allow_replace"))
    teacher_conflicts = _find_teacher_overlapping_slots(
        school_id,
        payload["teacher_id"],
        payload["day_of_week"],
        payload["start_time"],
        payload["end_time"],
        exclude_slot_id=slot_id,
    )
    if teacher_conflicts:
        return None, "teacher_conflict", _enrich_conflict_slot(teacher_conflicts[0], school_id)

    conflicts = _find_overlapping_slots(
        school_id,
        payload["class_id"],
        payload["day_of_week"],
        payload["start_time"],
        payload["end_time"],
        exclude_slot_id=slot_id,
    )
    if conflicts and not allow_replace:
        return None, "conflict", _enrich_conflict_slot(conflicts[0], school_id)
    if conflicts and allow_replace:
        for row in conflicts:
            (
                supabase_admin.table("teacher_timetable")
                .delete()
                .eq("id", row["id"])
                .eq("school_id", school_id)
                .execute()
            )
    try:
        result = (
            supabase_admin.table("teacher_timetable")
            .update(payload)
            .eq("id", slot_id)
            .eq("school_id", school_id)
            .execute()
        )
        if result.data:
            return result.data[0], None, None
        return None, "Slot not found.", None
    except Exception:
        return None, "Could not update slot.", None


def admin_delete_slot(slot_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("teacher_timetable")
            .delete()
            .eq("id", slot_id)
            .eq("school_id", school_id)
            .execute()
        )
        if result.data:
            return True, None
        return False, "Slot not found."
    except Exception:
        return False, "Could not delete slot."


def teachers_for_select(school_id: str) -> list:
    try:
        rows = (
            supabase_admin.table("teachers")
            .select("id, full_name")
            .eq("school_id", school_id)
            .eq("status", "active")
            .order("full_name")
            .execute()
            .data or []
        )
        return [{"id": t["id"], "name": t["full_name"]} for t in rows]
    except Exception:
        return []


def classes_for_select(school_id: str) -> list:
    from models.class_model import list_classes

    return [
        {"id": c["id"], "label": _class_label(c)}
        for c in list_classes(school_id)
    ]


def subjects_for_select(school_id: str) -> list:
    try:
        rows = (
            supabase_admin.table("subjects")
            .select("id, name")
            .eq("school_id", school_id)
            .order("name")
            .execute()
            .data or []
        )
        return [{"id": s["id"], "name": s["name"]} for s in rows]
    except Exception:
        return []
