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

HOURLY_START_OPTIONS = ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00"]
HOURLY_END_OPTIONS = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00"]

TIMETABLE_TABLE = "teacher_timetable"


def build_time_ranges() -> list:
    """Fixed 1-hour columns from 8 AM through 2 PM."""
    return [
        {"start": "08:00", "end": "09:00", "label": "8 AM – 9 AM"},
        {"start": "09:00", "end": "10:00", "label": "9 AM – 10 AM"},
        {"start": "10:00", "end": "11:00", "label": "10 AM – 11 AM"},
        {"start": "11:00", "end": "12:00", "label": "11 AM – 12 PM"},
        {"start": "12:00", "end": "13:00", "label": "12 PM – 1 PM"},
        {"start": "13:00", "end": "14:00", "label": "1 PM – 2 PM"},
    ]
