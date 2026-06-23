import re

from models.timetable.constants import DAYS, PASTEL_COLORS


def class_label(cls: dict) -> str:
    if not cls:
        return "—"
    name = cls.get("name") or cls.get("grade") or "Class"
    if cls.get("section"):
        return f"{name} — {cls['section']}"
    return name


def time_str(val) -> str:
    if not val:
        return ""
    s = str(val).strip()
    m = re.match(r"(\d{1,2}):(\d{2})", s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return s[:5] if len(s) >= 5 else s


def time_to_minutes(val) -> int:
    s = time_str(val)
    if not s or ":" not in s:
        return 0
    h, m = s.split(":", 1)
    return int(h) * 60 + int(m)


def times_overlap(slot_start: str, slot_end: str, range_start: str, range_end: str) -> bool:
    s0, s1 = time_to_minutes(slot_start), time_to_minutes(slot_end)
    r0, r1 = time_to_minutes(range_start), time_to_minutes(range_end)
    return s0 < r1 and s1 > r0


def slot_covers_range(row: dict, range_start: str, range_end: str) -> bool:
    return times_overlap(
        row.get("start_time"),
        row.get("end_time"),
        range_start,
        range_end,
    )


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
        "class_label": class_label(cls) if cls else row.get("class_label", "—"),
        "room": row.get("room") or "",
        "day_of_week": (row.get("day_of_week") or "monday").lower(),
        "start_time": time_str(row.get("start_time")),
        "end_time": time_str(row.get("end_time")),
        "color": color_for_subject(subject_name),
    }


def sort_slots(slots: list) -> list:
    return sorted(
        slots,
        key=lambda s: (
            DAYS.index(s["day_of_week"]) if s["day_of_week"] in DAYS else 99,
            s.get("start_time") or "",
        ),
    )


def normalize_teacher_slots(rows: list, teacher_name: str = None) -> list:
    out = []
    for row in rows or []:
        slot = normalize_slot(row, teacher_name=teacher_name)
        if row.get("class_info"):
            slot["class_label"] = class_label(row["class_info"])
        if row.get("subject_info"):
            slot["subject_name"] = row["subject_info"].get("name", slot["subject_name"])
        out.append(slot)
    return sort_slots(out)


def normalize_class_slots(rows: list) -> list:
    return sort_slots([normalize_slot(r) for r in (rows or [])])


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
