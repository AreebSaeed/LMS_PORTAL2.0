"""Challan document rendering — 3-copy layout matching school fee challan format."""

from datetime import datetime

DEFAULT_CHALLAN_TERMS = [
    "Payment must be made by the due date to avoid late charges.",
    "Late fee of Rs. 500 will be charged for each month of delay.",
    "Duplicate challan copies can be obtained from the school office within 7 working days.",
    "Post-dated cheques must include the school name and amount written clearly.",
]

COPY_LABELS = ("STUDENT COPY", "SCHOOL COPY", "BANK COPY")


def get_challan_terms(school: dict) -> list:
    raw = (school or {}).get("challan_terms") or ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return lines or DEFAULT_CHALLAN_TERMS


def _fmt_amount(val) -> str:
    n = float(val or 0)
    if n == int(n):
        return f"{int(n):,}"
    return f"{n:,.2f}"


def _pdf_safe(text) -> str:
    """Helvetica in FPDF only supports Latin-1; strip/replace common Unicode."""
    if text is None:
        return ""
    s = str(text)
    for src, dst in (
        ("\u2014", "-"), ("\u2013", "-"), ("\u2022", "*"),
        ("—", "-"), ("–", "-"), ("•", "*"),
    ):
        s = s.replace(src, dst)
    return s.encode("latin-1", "replace").decode("latin-1")


def build_challan_line_items(fee: dict) -> list:
    items = []
    mapping = [
        ("Tuition Fee", fee.get("tuition_fee")),
        ("Exam Fee", fee.get("exam_fee")),
        ("Transport Fee", fee.get("transport_fee")),
        ("Admission Fee", fee.get("admission_fee")),
        ("Annual Fee", fee.get("annual_fee")),
        ("Misc. Charges", fee.get("misc_charges")),
        ("Late Fee", fee.get("fine")),
    ]
    for label, val in mapping:
        if val and float(val) != 0:
            items.append({"label": label, "amount": float(val), "amount_display": _fmt_amount(val)})
    discount = float(fee.get("discount") or 0)
    if discount > 0:
        items.append({"label": "Discount", "amount": -discount, "amount_display": "-" + _fmt_amount(discount)})
    return items


def challan_billing_title(fee: dict) -> str:
    bm = fee.get("billing_month") or ""
    if bm:
        try:
            dt = datetime.strptime(str(bm)[:10], "%Y-%m-%d")
            return f"Fee Challan - {dt.strftime('%B %Y')}"
        except ValueError:
            pass
    return "Fee Challan"


def format_due_date(fee: dict) -> str:
    d = fee.get("due_date") or ""
    if not d:
        return "—"
    try:
        dt = datetime.strptime(str(d)[:10], "%Y-%m-%d")
        return dt.strftime("%d %B %Y")
    except ValueError:
        return str(d)[:10]


def student_class_label(fee: dict, student: dict) -> str:
    if fee.get("class_label") and fee["class_label"] != "—":
        return fee["class_label"].replace(" — ", " - ")
    g = (student or {}).get("class_grade") or ""
    sec = (student or {}).get("section") or ""
    if g and sec:
        return f"{g} - {sec}"
    return g or sec or "—"


def _student_field(student: dict, fee: dict, field: str, fallback="—") -> str:
    fee_student = fee.get("student") if isinstance(fee.get("student"), dict) else {}
    val = (student or {}).get(field) or fee_student.get(field)
    if val is None or str(val).strip() == "":
        return fallback
    return str(val).strip()


def build_challan_context(school: dict, fee: dict, student: dict) -> dict:
    items = build_challan_line_items(fee)
    total = float(fee.get("total_amount") or fee.get("amount") or 0)
    return {
        "school": school,
        "school_name": (school or {}).get("name") or "School",
        "billing_title": challan_billing_title(fee),
        "challan_number": fee.get("challan_number") or "—",
        "student_name": (student or {}).get("full_name") or fee.get("student_name") or "—",
        "registration_number": _student_field(student, fee, "admission_number"),
        "roll_number": _student_field(student, fee, "roll_number"),
        "class_label": student_class_label(fee, student),
        "due_date": format_due_date(fee),
        "line_items": items,
        "total": total,
        "total_formatted": _fmt_amount(total),
        "terms": get_challan_terms(school),
        "copy_labels": COPY_LABELS,
        "is_void": bool(fee.get("is_void")),
    }


def generate_challan_pdf(school: dict, fee: dict, student: dict) -> bytes:
    from fpdf import FPDF

    ctx = build_challan_context(school, fee, student)
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_margins(8, 8, 8)

    page_w = 297
    col_w = (page_w - 16) / 3
    start_x = 8
    y0 = 10
    navy = (30, 58, 95)
    grey_bg = (241, 245, 249)

    for i, copy_label in enumerate(COPY_LABELS):
        x = start_x + i * col_w
        if i > 0:
            pdf.set_draw_color(180, 180, 180)
            pdf.set_line_width(0.2)
            for dy in range(int(y0), 175, 4):
                pdf.line(x, dy, x, dy + 2)

        pdf.set_xy(x + 2, y0)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*navy)
        pdf.cell(col_w - 4, 7, _pdf_safe(ctx["school_name"]), align="C", ln=True)

        pdf.set_x(x + 2)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(col_w - 4, 5, _pdf_safe(ctx["billing_title"]), align="C", ln=True)

        pdf.ln(2)
        pdf.set_text_color(0, 0, 0)
        for label, val in [
            ("Challan No:", ctx["challan_number"]),
            ("Student Name:", ctx["student_name"]),
            ("Reg. No:", ctx["registration_number"]),
            ("Roll No:", ctx["roll_number"]),
            ("Class / Section:", ctx["class_label"]),
            ("Due Date:", ctx["due_date"]),
        ]:
            pdf.set_x(x + 4)
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(28, 4.5, label)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(col_w - 36, 4.5, _pdf_safe(val)[:40], ln=True)

        pdf.ln(1)
        pdf.set_fill_color(*grey_bg)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_x(x + 4)
        pdf.cell(col_w * 0.62 - 4, 6, "Description", border=1, fill=True)
        pdf.cell(col_w * 0.38, 6, "Amount (Rs.)", border=1, fill=True, align="R", ln=True)

        pdf.set_font("Helvetica", "", 8)
        for item in ctx["line_items"]:
            pdf.set_x(x + 4)
            pdf.cell(col_w * 0.62 - 4, 5.5, _pdf_safe(item["label"]), border="LR")
            pdf.cell(col_w * 0.38, 5.5, _pdf_safe(_fmt_amount(item["amount"])), border="LR", align="R", ln=True)

        pdf.set_x(x + 4)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(col_w * 0.62 - 4, 6, "Total", border=1)
        pdf.cell(col_w * 0.38, 6, _pdf_safe(ctx["total_formatted"]), border=1, align="R", ln=True)

        pdf.ln(4)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_x(x + 4)
        pdf.cell((col_w - 8) / 2, 5, "Cashier Sign: __________")
        pdf.cell((col_w - 8) / 2, 5, "Date: __________", align="R", ln=True)

        pdf.set_xy(x + 2, 168)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*navy)
        pdf.cell(col_w - 4, 5, _pdf_safe(f"- {copy_label} -"), align="C")

    pdf.set_text_color(0, 0, 0)
    pdf.set_draw_color(200, 214, 229)
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(8, 178, page_w - 16, 28, style="DF")
    pdf.set_xy(12, 181)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*navy)
    pdf.cell(0, 5, "Terms & Conditions", ln=True)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(60, 60, 60)
    for term in ctx["terms"]:
        pdf.set_x(14)
        pdf.cell(0, 4, _pdf_safe(f"* {term}"), ln=True)

    if ctx["is_void"]:
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(220, 38, 38)
        pdf.text(110, 100, "VOID")

    out = pdf.output()
    if isinstance(out, bytes):
        return out
    if isinstance(out, bytearray):
        return bytes(out)
    return str(out).encode("latin-1")
