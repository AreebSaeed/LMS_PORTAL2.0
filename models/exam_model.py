from datetime import datetime, timezone
from io import BytesIO
from models.supabase_client import supabase_admin
from models.attendance_model import get_students_for_class
from models.teacher_model import get_subjects, get_classes, get_assigned_class_ids
from models.class_model import list_classes, get_class_subjects

EXAM_ADMIN_TYPES = [
    ("midterm", "Mid Term"),
    ("final", "Final Term"),
]

EXAM_TERM_TYPES = EXAM_ADMIN_TYPES

SUBMISSION_STATUSES = {
    "pending": "Pending",
    "in_progress": "In Progress",
    "submitted": "Awaiting Approval",
    "approved": "Approved",
    "rejected": "Rejected",
}

GRADE_SCALE = [
    (90, "A+"),
    (80, "A"),
    (70, "B"),
    (60, "C"),
    (50, "D"),
    (0, "F"),
]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _class_label(cls: dict) -> str:
    if not cls:
        return "—"
    name = cls.get("name") or cls.get("grade") or "Class"
    if cls.get("section"):
        return f"{name} — {cls['section']}"
    return name


def _class_map(school_id: str) -> dict:
    return {c["id"]: c for c in list_classes(school_id)}


def calc_grade(percentage: float) -> str:
    for threshold, grade in GRADE_SCALE:
        if percentage >= threshold:
            return grade
    return "F"


def calc_subject_grade(marks: float, max_marks: float) -> str:
    if max_marks <= 0:
        return "—"
    return calc_grade((marks / max_marks) * 100)


def list_exam_terms(school_id: str, class_id: str = None, limit=50):
    try:
        q = (
            supabase_admin.table("exam_terms")
            .select("*")
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if class_id:
            q = q.eq("class_id", class_id)
        return q.execute().data or []
    except Exception:
        return []


def get_exam_term(term_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("exam_terms")
            .select("*")
            .eq("id", term_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def create_exam_term(school_id: str, data: dict, created_by: str = None):
    payload = {
        "school_id": school_id,
        "name": data["name"].strip(),
        "term_type": data.get("term_type") or "monthly_test",
        "academic_year": (data.get("academic_year") or "").strip() or None,
        "class_id": data.get("class_id") or None,
        "start_date": data.get("start_date") or None,
        "end_date": data.get("end_date") or None,
        "created_by": created_by,
        "updated_at": _now_iso(),
    }
    try:
        result = supabase_admin.table("exam_terms").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def update_exam_term(term_id: str, school_id: str, data: dict):
    payload = {
        "name": data["name"].strip(),
        "term_type": data.get("term_type") or "monthly_test",
        "academic_year": (data.get("academic_year") or "").strip() or None,
        "class_id": data.get("class_id") or None,
        "start_date": data.get("start_date") or None,
        "end_date": data.get("end_date") or None,
        "updated_at": _now_iso(),
    }
    try:
        result = (
            supabase_admin.table("exam_terms")
            .update(payload)
            .eq("id", term_id)
            .eq("school_id", school_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_exam_papers(term_id: str, school_id: str):
    try:
        rows = (
            supabase_admin.table("exam_papers")
            .select("*")
            .eq("exam_term_id", term_id)
            .eq("school_id", school_id)
            .order("sort_order")
            .execute()
            .data or []
        )
    except Exception:
        return []

    subject_ids = {r["subject_id"] for r in rows if r.get("subject_id")}
    smap = {}
    if subject_ids:
        subjects = supabase_admin.table("subjects").select("id, name, code").in_("id", list(subject_ids)).execute().data or []
        smap = {s["id"]: s for s in subjects}

    for row in rows:
        sub = smap.get(row.get("subject_id"), {})
        row["subject_name"] = sub.get("name", "Subject")
        row["subject_code"] = sub.get("code")
    return rows


def add_exam_paper(term_id: str, school_id: str, data: dict):
    payload = {
        "school_id": school_id,
        "exam_term_id": term_id,
        "subject_id": data["subject_id"],
        "max_marks": float(data.get("max_marks") or 100),
        "pass_marks": float(data.get("pass_marks") or 33),
        "weight_percent": float(data.get("weight_percent") or 100),
        "exam_date": data.get("exam_date") or None,
        "sort_order": int(data.get("sort_order") or 0),
    }
    try:
        result = supabase_admin.table("exam_papers").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def delete_exam_paper(paper_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("exam_papers")
            .delete()
            .eq("id", paper_id)
            .eq("school_id", school_id)
            .execute()
        )
        return bool(result.data)
    except Exception:
        return False


def get_marks_matrix(term_id: str, school_id: str, class_id: str):
    papers = get_exam_papers(term_id, school_id)
    students = get_students_for_class(school_id, class_id=class_id)
    if not papers or not students:
        return papers, students, {}

    try:
        rows = (
            supabase_admin.table("exam_subject_marks")
            .select("*")
            .eq("exam_term_id", term_id)
            .eq("school_id", school_id)
            .execute()
            .data or []
        )
    except Exception:
        rows = []

    matrix = {}
    for r in rows:
        matrix[(r["student_id"], r["exam_paper_id"])] = r
    return papers, students, matrix


def save_subject_marks(term_id: str, school_id: str, paper_id: str, marks: dict, entered_by: str = None):
    paper = None
    for p in get_exam_papers(term_id, school_id):
        if p["id"] == paper_id:
            paper = p
            break
    if not paper:
        return 0

    max_marks = float(paper.get("max_marks") or 100)
    saved = 0
    for student_id, val in marks.items():
        if val is None or val == "":
            continue
        try:
            marks_num = float(val)
        except (TypeError, ValueError):
            continue
        grade = calc_subject_grade(marks_num, max_marks)
        payload = {
            "school_id": school_id,
            "exam_paper_id": paper_id,
            "exam_term_id": term_id,
            "student_id": student_id,
            "marks_obtained": marks_num,
            "grade": grade,
            "entered_by": entered_by,
            "updated_at": _now_iso(),
        }
        try:
            supabase_admin.table("exam_subject_marks").upsert(
                payload, on_conflict="exam_paper_id,student_id"
            ).execute()
            saved += 1
        except Exception:
            pass

    if saved:
        try:
            term = get_exam_term(term_id, school_id)
            if term and term.get("submission_status") in ("pending", "rejected", None):
                supabase_admin.table("exam_terms").update({
                    "submission_status": "in_progress",
                    "updated_at": _now_iso(),
                }).eq("id", term_id).eq("school_id", school_id).execute()
        except Exception:
            pass
    return saved


def calculate_term_results(term_id: str, school_id: str, class_id: str):
    papers = get_exam_papers(term_id, school_id)
    students = get_students_for_class(school_id, class_id=class_id)
    if not papers or not students:
        return 0

    try:
        all_marks = (
            supabase_admin.table("exam_subject_marks")
            .select("*")
            .eq("exam_term_id", term_id)
            .eq("school_id", school_id)
            .execute()
            .data or []
        )
    except Exception:
        all_marks = []

    marks_by_student = {}
    for m in all_marks:
        sid = m["student_id"]
        pid = m["exam_paper_id"]
        marks_by_student.setdefault(sid, {})[pid] = m

    paper_map = {p["id"]: p for p in papers}
    student_totals = []

    for student in students:
        sid = student["id"]
        total_obtained = 0.0
        total_max = 0.0
        for paper in papers:
            pid = paper["id"]
            max_m = float(paper.get("max_marks") or 100)
            weight = float(paper.get("weight_percent") or 100) / 100.0
            weighted_max = max_m * weight
            total_max += weighted_max
            rec = marks_by_student.get(sid, {}).get(pid)
            if rec and rec.get("marks_obtained") is not None:
                total_obtained += float(rec["marks_obtained"]) * weight

        pct = round((total_obtained / total_max) * 100, 2) if total_max > 0 else 0
        grade = calc_grade(pct)
        payload = {
            "school_id": school_id,
            "exam_term_id": term_id,
            "student_id": sid,
            "class_id": class_id,
            "total_obtained": round(total_obtained, 2),
            "total_max": round(total_max, 2),
            "percentage": pct,
            "overall_grade": grade,
            "updated_at": _now_iso(),
        }
        try:
            supabase_admin.table("exam_term_results").upsert(
                payload, on_conflict="exam_term_id,student_id"
            ).execute()
        except Exception:
            pass
        student_totals.append({**payload, "student": student})

    student_totals.sort(key=lambda x: x["percentage"], reverse=True)
    rank = 0
    prev_pct = None
    for i, row in enumerate(student_totals):
        if row["percentage"] != prev_pct:
            rank = i + 1
            prev_pct = row["percentage"]
        try:
            supabase_admin.table("exam_term_results").update({
                "class_rank": rank,
                "updated_at": _now_iso(),
            }).eq("exam_term_id", term_id).eq("student_id", row["student_id"]).execute()
        except Exception:
            pass

    return len(student_totals)


def get_term_results(term_id: str, school_id: str):
    try:
        rows = (
            supabase_admin.table("exam_term_results")
            .select("*")
            .eq("exam_term_id", term_id)
            .eq("school_id", school_id)
            .order("class_rank")
            .execute()
            .data or []
        )
    except Exception:
        return []

    student_ids = {r["student_id"] for r in rows}
    smap = {}
    if student_ids:
        students = (
            supabase_admin.table("students")
            .select("id, full_name, roll_number, admission_number")
            .in_("id", list(student_ids))
            .execute()
            .data or []
        )
        smap = {s["id"]: s for s in students}

    return [{**r, "student": smap.get(r["student_id"], {})} for r in rows]


def get_student_term_result(term_id: str, student_id: str, school_id: str):
    try:
        rows = (
            supabase_admin.table("exam_term_results")
            .select("*")
            .eq("exam_term_id", term_id)
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .limit(1)
            .execute()
            .data or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def get_student_subject_marks(term_id: str, student_id: str, school_id: str):
    papers = get_exam_papers(term_id, school_id)
    try:
        rows = (
            supabase_admin.table("exam_subject_marks")
            .select("*")
            .eq("exam_term_id", term_id)
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .execute()
            .data or []
        )
    except Exception:
        rows = []

    marks_map = {r["exam_paper_id"]: r for r in rows}
    detail = []
    for paper in papers:
        m = marks_map.get(paper["id"], {})
        detail.append({
            **paper,
            "marks_obtained": m.get("marks_obtained"),
            "grade": m.get("grade"),
            "remarks": m.get("remarks"),
        })
    return detail


def publish_term_results(term_id: str, school_id: str):
    try:
        supabase_admin.table("exam_terms").update({
            "is_published": True,
            "updated_at": _now_iso(),
        }).eq("id", term_id).eq("school_id", school_id).execute()

        supabase_admin.table("exam_term_results").update({
            "result_status": "published",
            "published_at": _now_iso(),
            "updated_at": _now_iso(),
        }).eq("exam_term_id", term_id).eq("school_id", school_id).execute()
        return True
    except Exception:
        return False


def share_results_with_parents(term_id: str, school_id: str, sent_by: str = None):
    term = get_exam_term(term_id, school_id)
    if not term:
        return 0, "Exam term not found."

    results = get_term_results(term_id, school_id)
    if not results:
        return 0, "No results to share. Calculate results first."

    from models.parent_model import send_notification

    notified = 0
    for result in results:
        student = result.get("student") or {}
        student_id = result["student_id"]
        student_name = student.get("full_name", "Your child")
        try:
            links = (
                supabase_admin.table("parent_student_links")
                .select("parent_id")
                .eq("student_id", student_id)
                .eq("school_id", school_id)
                .execute()
                .data or []
            )
            msg = (
                f"{student_name}'s {term['name']} result is ready. "
                f"Total: {result['total_obtained']}/{result['total_max']} "
                f"({result['percentage']}%) — Grade {result['overall_grade']}, "
                f"Rank #{result.get('class_rank') or '—'}."
            )
            for link in links:
                if send_notification(
                    link["parent_id"], school_id,
                    f"Result Published — {term['name']}", msg, sent_by,
                ):
                    notified += 1
        except Exception:
            continue

    try:
        supabase_admin.table("exam_term_results").update({
            "shared_with_parents": True,
            "updated_at": _now_iso(),
        }).eq("exam_term_id", term_id).eq("school_id", school_id).execute()
    except Exception:
        pass

    return notified, None


def get_student_result_history(student_id: str, school_id: str, published_only=True):
    try:
        q = (
            supabase_admin.table("exam_term_results")
            .select("*")
            .eq("student_id", student_id)
            .eq("school_id", school_id)
            .order("published_at", desc=True)
        )
        if published_only:
            q = q.eq("result_status", "published")
        rows = q.execute().data or []
    except Exception:
        return []

    term_ids = {r["exam_term_id"] for r in rows}
    term_map = {}
    if term_ids:
        terms = supabase_admin.table("exam_terms").select("*").in_("id", list(term_ids)).execute().data or []
        term_map = {t["id"]: t for t in terms}

    return [{**r, "term": term_map.get(r["exam_term_id"], {})} for r in rows]


def teacher_can_access_term(teacher_id: str, term: dict) -> bool:
    if not term.get("class_id"):
        return True
    return term["class_id"] in get_assigned_class_ids(teacher_id)


def generate_result_pdf(school: dict, term: dict, student: dict, result: dict, subject_marks: list) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, school.get("name", "School") if school else "School", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "RESULT CARD", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 11)
    lines = [
        f"Exam: {term.get('name', '')} ({term.get('term_type', '').replace('_', ' ').title()})",
        f"Student: {student.get('full_name', '')}",
        f"Admission No: {student.get('admission_number', '')}  Roll: {student.get('roll_number') or '-'}",
        f"Class: {student.get('class_grade', '')}-{student.get('section') or ''}",
        f"Academic Year: {term.get('academic_year') or '-'}",
    ]
    for line in lines:
        pdf.cell(0, 8, line, ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(80, 8, "Subject", border=1)
    pdf.cell(30, 8, "Marks", border=1)
    pdf.cell(30, 8, "Max", border=1)
    pdf.cell(30, 8, "Grade", border=1, ln=True)

    pdf.set_font("Helvetica", "", 10)
    for sm in subject_marks:
        pdf.cell(80, 8, sm.get("subject_name", ""), border=1)
        pdf.cell(30, 8, str(sm.get("marks_obtained") if sm.get("marks_obtained") is not None else "-"), border=1)
        pdf.cell(30, 8, str(sm.get("max_marks", "")), border=1)
        pdf.cell(30, 8, str(sm.get("grade") or "-"), border=1, ln=True)

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"Total: {result.get('total_obtained')}/{result.get('total_max')}", ln=True)
    pdf.cell(0, 8, f"Percentage: {result.get('percentage')}%", ln=True)
    pdf.cell(0, 8, f"Grade: {result.get('overall_grade')}  |  Class Rank: #{result.get('class_rank') or '-'}", ln=True)

    return pdf.output()


# ── School-wide exam groups ──────────────────────────────────────────────────


def list_exam_groups(
    school_id: str,
    limit=100,
    published_only: bool = None,
    academic_year: str = None,
    term_type: str = None,
):
    try:
        q = (
            supabase_admin.table("exam_groups")
            .select("*")
            .eq("school_id", school_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if published_only is True:
            q = q.eq("is_published", True)
        elif published_only is False:
            q = q.eq("is_published", False)
        if academic_year:
            q = q.eq("academic_year", academic_year)
        if term_type in ("midterm", "final"):
            q = q.eq("term_type", term_type)
        groups = q.execute().data or []
    except Exception:
        return []

    if not groups:
        return []

    group_ids = [g["id"] for g in groups]
    try:
        terms = (
            supabase_admin.table("exam_terms")
            .select("id, exam_group_id, submission_status, is_published, class_id")
            .eq("school_id", school_id)
            .in_("exam_group_id", group_ids)
            .execute()
            .data or []
        )
    except Exception:
        terms = []

    term_ids = [t["id"] for t in terms]
    results_by_term = {}
    if term_ids:
        try:
            result_rows = (
                supabase_admin.table("exam_term_results")
                .select("exam_term_id, percentage, result_status")
                .eq("school_id", school_id)
                .in_("exam_term_id", term_ids)
                .execute()
                .data or []
            )
            for r in result_rows:
                results_by_term.setdefault(r["exam_term_id"], []).append(r)
        except Exception:
            pass

    by_group = {}
    for t in terms:
        gid = t.get("exam_group_id")
        by_group.setdefault(gid, []).append(t)

    for g in groups:
        gterms = by_group.get(g["id"], [])
        g["class_count"] = len(gterms)
        g["approved_count"] = sum(1 for t in gterms if t.get("submission_status") == "approved")
        g["submitted_count"] = sum(1 for t in gterms if t.get("submission_status") == "submitted")

        all_pcts = []
        published_students = 0
        for t in gterms:
            for r in results_by_term.get(t["id"], []):
                if r.get("percentage") is not None:
                    all_pcts.append(float(r["percentage"]))
                if r.get("result_status") == "published":
                    published_students += 1
        g["total_students"] = len(all_pcts)
        g["published_students"] = published_students
        g["school_avg"] = round(sum(all_pcts) / len(all_pcts), 1) if all_pcts else None

    return groups


def get_exam_history_years(school_id: str):
    try:
        rows = (
            supabase_admin.table("exam_groups")
            .select("academic_year")
            .eq("school_id", school_id)
            .eq("is_published", True)
            .execute()
            .data or []
        )
    except Exception:
        return []
    years = sorted(
        {r["academic_year"] for r in rows if r.get("academic_year")},
        reverse=True,
    )
    return years


def get_exam_history_summary(school_id: str):
    try:
        all_groups = (
            supabase_admin.table("exam_groups")
            .select("id, is_published, term_type")
            .eq("school_id", school_id)
            .execute()
            .data or []
        )
    except Exception:
        all_groups = []

    published = [g for g in all_groups if g.get("is_published")]
    return {
        "total_exams": len(all_groups),
        "published_count": len(published),
        "active_count": len(all_groups) - len(published),
        "midterm_count": sum(1 for g in published if g.get("term_type") == "midterm"),
        "final_count": sum(1 for g in published if g.get("term_type") == "final"),
    }


def get_group_history_detail(group_id: str, school_id: str):
    group = get_exam_group(group_id, school_id)
    if not group:
        return None

    terms = get_terms_for_group(group_id, school_id)
    class_records = []
    all_pcts = []

    for term in terms:
        results = get_term_results(term["id"], school_id)
        pcts = [float(r["percentage"]) for r in results if r.get("percentage") is not None]
        avg = round(sum(pcts) / len(pcts), 1) if pcts else None
        top = results[0] if results else None
        if pcts:
            all_pcts.extend(pcts)
        class_records.append({
            "term": term,
            "class_label": term["class_label"],
            "results_count": len(results),
            "class_avg": avg,
            "top_student": (top.get("student") or {}).get("full_name") if top else None,
            "top_percentage": top.get("percentage") if top else None,
            "top_grade": top.get("overall_grade") if top else None,
        })

    return {
        "group": group,
        "class_records": class_records,
        "school_avg": round(sum(all_pcts) / len(all_pcts), 1) if all_pcts else None,
        "total_students": len(all_pcts),
    }


def get_exam_group(group_id: str, school_id: str):
    try:
        result = (
            supabase_admin.table("exam_groups")
            .select("*")
            .eq("id", group_id)
            .eq("school_id", school_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


def get_terms_for_group(group_id: str, school_id: str):
    try:
        terms = (
            supabase_admin.table("exam_terms")
            .select("*")
            .eq("exam_group_id", group_id)
            .eq("school_id", school_id)
            .order("name")
            .execute()
            .data or []
        )
    except Exception:
        return []

    cmap = _class_map(school_id)
    enriched = []
    for term in terms:
        cls = cmap.get(term.get("class_id"), {})
        results = get_term_results(term["id"], school_id)
        enriched.append({
            **term,
            "class_label": _class_label(cls),
            "class_info": cls,
            "results_count": len(results),
            "papers_count": len(get_exam_papers(term["id"], school_id)),
        })
    return enriched


def create_school_exam(school_id: str, data: dict, created_by: str = None):
    term_type = data.get("term_type") or "midterm"
    if term_type not in ("midterm", "final"):
        return None, "Exam type must be Mid Term or Final Term."

    name = data["name"].strip()
    if not name:
        return None, "Exam name is required."

    weight = float(data.get("weight_percent") or 100)
    classes = list_classes(school_id)
    if not classes:
        return None, "No classes found. Create classes before scheduling an exam."

    group_payload = {
        "school_id": school_id,
        "name": name,
        "term_type": term_type,
        "weight_percent": weight,
        "academic_year": (data.get("academic_year") or "").strip() or None,
        "start_date": data.get("start_date") or None,
        "end_date": data.get("end_date") or None,
        "created_by": created_by,
        "updated_at": _now_iso(),
    }
    try:
        group_result = supabase_admin.table("exam_groups").insert(group_payload).execute()
        group = group_result.data[0] if group_result.data else None
    except Exception:
        return None, "Could not create exam. Run sql/module14_exam_groups.sql in Supabase."

    if not group:
        return None, "Could not create exam."

    created_terms = 0
    for idx, cls in enumerate(classes):
        term_name = f"{name} — {_class_label(cls)}"
        term_payload = {
            "school_id": school_id,
            "exam_group_id": group["id"],
            "name": term_name,
            "term_type": term_type,
            "academic_year": group_payload["academic_year"],
            "class_id": cls["id"],
            "start_date": group_payload["start_date"],
            "end_date": group_payload["end_date"],
            "submission_status": "pending",
            "created_by": created_by,
            "updated_at": _now_iso(),
        }
        try:
            term_result = supabase_admin.table("exam_terms").insert(term_payload).execute()
            term = term_result.data[0] if term_result.data else None
        except Exception:
            continue
        if not term:
            continue
        created_terms += 1
        subjects = get_class_subjects(cls["id"], school_id)
        for sort_i, sub in enumerate(subjects):
            add_exam_paper(term["id"], school_id, {
                "subject_id": sub["id"],
                "max_marks": 100,
                "pass_marks": 33,
                "weight_percent": 100,
                "sort_order": sort_i,
            })

    if created_terms == 0:
        try:
            supabase_admin.table("exam_groups").delete().eq("id", group["id"]).execute()
        except Exception:
            pass
        return None, "Could not create class exam records."

    return group, None


def submit_class_results(term_id: str, school_id: str, submitted_by: str = None):
    term = get_exam_term(term_id, school_id)
    if not term:
        return False, "Exam not found."
    if term.get("submission_status") in ("submitted", "approved"):
        return False, "Results already submitted for approval."

    papers = get_exam_papers(term_id, school_id)
    if not papers:
        return False, "No subjects assigned to this class exam."

    class_id = term.get("class_id")
    count = calculate_term_results(term_id, school_id, class_id)
    if count == 0:
        return False, "Enter marks for students before submitting."

    try:
        supabase_admin.table("exam_terms").update({
            "submission_status": "submitted",
            "submitted_by": submitted_by,
            "submitted_at": _now_iso(),
            "rejection_note": None,
            "updated_at": _now_iso(),
        }).eq("id", term_id).eq("school_id", school_id).execute()
        return True, None
    except Exception:
        return False, "Could not submit results."


def approve_class_results(term_id: str, school_id: str):
    term = get_exam_term(term_id, school_id)
    if not term:
        return False, "Exam not found."
    if term.get("submission_status") != "submitted":
        return False, "Only submitted results can be approved."

    try:
        supabase_admin.table("exam_terms").update({
            "submission_status": "approved",
            "approved_at": _now_iso(),
            "updated_at": _now_iso(),
        }).eq("id", term_id).eq("school_id", school_id).execute()
        return True, None
    except Exception:
        return False, "Approval failed."


def reject_class_results(term_id: str, school_id: str, note: str = ""):
    term = get_exam_term(term_id, school_id)
    if not term:
        return False, "Exam not found."
    if term.get("submission_status") != "submitted":
        return False, "Only submitted results can be rejected."

    try:
        supabase_admin.table("exam_terms").update({
            "submission_status": "rejected",
            "rejection_note": (note or "").strip() or None,
            "updated_at": _now_iso(),
        }).eq("id", term_id).eq("school_id", school_id).execute()
        return True, None
    except Exception:
        return False, "Rejection failed."


def publish_exam_group(group_id: str, school_id: str, published_by: str = None):
    group = get_exam_group(group_id, school_id)
    if not group:
        return False, "Exam not found."
    if group.get("is_published"):
        return False, "Results are already published."

    terms = get_terms_for_group(group_id, school_id)
    approved = [t for t in terms if t.get("submission_status") == "approved"]
    if not approved:
        return False, "Approve at least one class result before publishing."

    for term in approved:
        publish_term_results(term["id"], school_id)
        share_results_with_parents(term["id"], school_id, published_by)

    try:
        supabase_admin.table("exam_groups").update({
            "is_published": True,
            "published_at": _now_iso(),
            "updated_at": _now_iso(),
        }).eq("id", group_id).eq("school_id", school_id).execute()
    except Exception:
        return False, "Publish failed."

    type_label = "Mid Term" if group.get("term_type") == "midterm" else "Final Term"
    from models.admin_model import create_school_announcement
    create_school_announcement(
        school_id,
        published_by,
        f"{type_label} Results Published — {group['name']}",
        (
            f"The {type_label} examination results for {group['name']} "
            f"({group.get('academic_year') or 'current academic year'}) have been published. "
            "Please log in to the parent or student portal to view your child's result card."
        ),
    )
    return True, None


def get_exam_group_analytics(group_id: str, school_id: str):
    group = get_exam_group(group_id, school_id)
    if not group:
        return None

    terms = get_terms_for_group(group_id, school_id)
    class_averages = []
    grade_distribution = {g: 0 for _, g in GRADE_SCALE}
    subject_analytics = []
    submission_stats = {k: 0 for k in SUBMISSION_STATUSES}
    top_performers = []

    for term in terms:
        status = term.get("submission_status") or "pending"
        submission_stats[status] = submission_stats.get(status, 0) + 1

        results = get_term_results(term["id"], school_id)
        if not results:
            class_averages.append({
                "class_id": term.get("class_id"),
                "label": term["class_label"],
                "avg": 0,
                "students": 0,
                "status": status,
                "term_id": term["id"],
            })
            continue

        avg_pct = round(sum(r["percentage"] for r in results) / len(results), 1)
        class_averages.append({
            "class_id": term.get("class_id"),
            "label": term["class_label"],
            "avg": avg_pct,
            "students": len(results),
            "status": status,
            "term_id": term["id"],
        })

        for r in results:
            grade = r.get("overall_grade") or "F"
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
            top_performers.append({
                "student_name": (r.get("student") or {}).get("full_name", "Student"),
                "class_label": term["class_label"],
                "percentage": r["percentage"],
                "grade": grade,
                "term_id": term["id"],
                "student_id": r["student_id"],
            })

        papers = get_exam_papers(term["id"], school_id)
        try:
            marks_rows = (
                supabase_admin.table("exam_subject_marks")
                .select("exam_paper_id, marks_obtained")
                .eq("exam_term_id", term["id"])
                .eq("school_id", school_id)
                .execute()
                .data or []
            )
        except Exception:
            marks_rows = []

        by_paper = {}
        for m in marks_rows:
            by_paper.setdefault(m["exam_paper_id"], []).append(float(m["marks_obtained"] or 0))

        for paper in papers:
            scores = by_paper.get(paper["id"], [])
            if not scores:
                continue
            max_m = float(paper.get("max_marks") or 100)
            pcts = [(s / max_m) * 100 for s in scores if max_m > 0]
            avg_sub = round(sum(pcts) / len(pcts), 1) if pcts else 0
            pass_m = float(paper.get("pass_marks") or 33)
            pass_rate = round(
                sum(1 for s in scores if s >= pass_m) / len(scores) * 100, 1
            ) if scores else 0
            subject_analytics.append({
                "class_label": term["class_label"],
                "subject_name": paper.get("subject_name", "Subject"),
                "avg_pct": avg_sub,
                "pass_rate": pass_rate,
                "students": len(scores),
            })

    top_performers.sort(key=lambda x: x["percentage"], reverse=True)
    return {
        "group": group,
        "terms": terms,
        "class_averages": class_averages,
        "grade_distribution": grade_distribution,
        "subject_analytics": subject_analytics,
        "submission_stats": submission_stats,
        "top_performers": top_performers[:15],
    }
