from datetime import date
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, abort, Response,
)
from controllers.auth_helpers import fee_staff_required
from models.school_model import get_school_by_id
from models.student_model import get_classes_for_school
from models.fee_model import (
    PAYMENT_METHODS,
    get_dashboard_stats,
    list_fee_structures,
    get_fee_structure,
    save_fee_structure,
    generate_monthly_challans,
    list_fees,
    get_fee_record,
    get_fee_payments,
    record_payment,
    update_fee_adjustments,
    get_receipt_for_fee,
    send_fee_reminder,
    send_bulk_reminders,
    generate_receipt_pdf,
)

fee_bp = Blueprint("fees", __name__)


def _ctx(active_nav: str):
    school_id = session["school_id"]
    role = session.get("role")
    return {
        "school": get_school_by_id(school_id),
        "school_id": school_id,
        "full_name": session.get("full_name"),
        "role": role,
        "role_label": "Admin" if role == "school_admin" else "Accountant",
        "active_nav": active_nav,
        "classes": get_classes_for_school(school_id),
        "payment_methods": PAYMENT_METHODS,
    }


@fee_bp.route("/")
@fee_staff_required
def index():
    school_id = session["school_id"]
    stats = get_dashboard_stats(school_id)
    ctx = _ctx("fees")
    ctx.update({"page_title": "Fee Management", **stats})
    return render_template("fees/dashboard.html", **ctx)


@fee_bp.route("/structure", methods=["GET", "POST"])
@fee_staff_required
def structure():
    school_id = session["school_id"]
    class_id = request.args.get("class_id") or request.form.get("class_id") or None
    if class_id == "":
        class_id = None

    if request.method == "POST":
        data = {
            "name": request.form.get("name", ""),
            "tuition_fee": request.form.get("tuition_fee", 0),
            "admission_fee": request.form.get("admission_fee", 0),
            "annual_fee": request.form.get("annual_fee", 0),
            "exam_fee": request.form.get("exam_fee", 0),
            "transport_fee": request.form.get("transport_fee", 0),
        }
        if save_fee_structure(school_id, data, class_id):
            flash("Fee structure saved.", "success")
            return redirect(url_for("fees.structure", class_id=class_id or ""))
        flash("Could not save fee structure.", "error")

    current = get_fee_structure(school_id, class_id)
    ctx = _ctx("structure")
    ctx.update({
        "structures": list_fee_structures(school_id),
        "current": current,
        "selected_class_id": class_id,
        "page_title": "Fee Structure",
    })
    return render_template("fees/structure.html", **ctx)


@fee_bp.route("/generate", methods=["GET", "POST"])
@fee_staff_required
def generate():
    school_id = session["school_id"]
    today = date.today()

    if request.method == "POST":
        class_id = request.form.get("class_id")
        if not class_id:
            flash("Select a class.", "error")
        else:
            year = int(request.form.get("year", today.year))
            month = int(request.form.get("month", today.month))
            include = {
                "tuition": request.form.get("include_tuition") == "on",
                "transport": request.form.get("include_transport") == "on",
                "admission": request.form.get("include_admission") == "on",
                "annual": request.form.get("include_annual") == "on",
                "exam": request.form.get("include_exam") == "on",
            }
            due_day = int(request.form.get("due_day") or 10)
            count, err = generate_monthly_challans(
                school_id, class_id, year, month,
                session["user_id"], include, due_day,
            )
            if err:
                flash(err, "error")
            else:
                flash(f"Generated {count} fee challan(s).", "success")
                return redirect(url_for("fees.challans", class_id=class_id))

    ctx = _ctx("generate")
    ctx.update({
        "year": today.year,
        "month": today.month,
        "page_title": "Generate Challans",
    })
    return render_template("fees/generate.html", **ctx)


@fee_bp.route("/challans")
@fee_staff_required
def challans():
    school_id = session["school_id"]
    status = request.args.get("status") or None
    class_id = request.args.get("class_id") or None
    billing_month = request.args.get("billing_month") or None

    ctx = _ctx("challans")
    ctx.update({
        "fees": list_fees(school_id, status=status, class_id=class_id, billing_month=billing_month, limit=200),
        "filter_status": status,
        "filter_class": class_id,
        "filter_month": billing_month,
        "page_title": "Fee Challans",
    })
    return render_template("fees/challans.html", **ctx)


@fee_bp.route("/challans/<fee_id>", methods=["GET", "POST"])
@fee_staff_required
def challan_detail(fee_id):
    school_id = session["school_id"]
    fee = get_fee_record(fee_id, school_id)
    if not fee:
        abort(404)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "pay":
            amount = request.form.get("amount", 0)
            method = request.form.get("payment_method", "cash")
            notes = request.form.get("notes", "")
            result, err = record_payment(fee_id, school_id, amount, method, session["user_id"], notes)
            if err:
                flash(err, "error")
            else:
                flash(f"Payment recorded. Receipt: {result['receipt_number']}", "success")
                return redirect(url_for("fees.challan_detail", fee_id=fee_id))
        elif action == "discount":
            discount = request.form.get("discount", 0)
            _, err = update_fee_adjustments(fee_id, school_id, discount=discount)
            if err:
                flash(err, "error")
            else:
                flash("Discount updated.", "success")
                return redirect(url_for("fees.challan_detail", fee_id=fee_id))
        elif action == "fine":
            fine = request.form.get("fine", 0)
            _, err = update_fee_adjustments(fee_id, school_id, fine=fine)
            if err:
                flash(err, "error")
            else:
                flash("Late fee / fine updated.", "success")
                return redirect(url_for("fees.challan_detail", fee_id=fee_id))
        elif action == "remind":
            ok, msg = send_fee_reminder(fee_id, school_id, session["user_id"], request.form.get("message"))
            flash(msg, "success" if ok else "error")
            return redirect(url_for("fees.challan_detail", fee_id=fee_id))

    ctx = _ctx("challans")
    ctx.update({
        "fee": get_fee_record(fee_id, school_id),
        "payments": get_fee_payments(fee_id, school_id),
        "receipt": get_receipt_for_fee(fee_id, school_id),
        "page_title": f"Challan {fee.get('challan_number') or fee_id[:8]}",
    })
    return render_template("fees/challan_detail.html", **ctx)


@fee_bp.route("/reports/<report_type>")
@fee_staff_required
def reports(report_type):
    school_id = session["school_id"]
    valid = ("paid", "unpaid", "defaulters")
    if report_type not in valid:
        abort(404)

    if report_type == "paid":
        fees = list_fees(school_id, status="paid", limit=500)
    elif report_type == "defaulters":
        fees = list_fees(school_id, status="overdue", limit=500)
    else:
        all_fees = list_fees(school_id, limit=500)
        fees = [f for f in all_fees if f.get("status") in ("pending", "partial", "overdue")]

    titles = {"paid": "Paid Students", "unpaid": "Unpaid Students", "defaulters": "Fee Defaulters"}
    ctx = _ctx("reports")
    ctx.update({
        "fees": fees,
        "report_type": report_type,
        "page_title": titles[report_type],
    })
    return render_template("fees/reports.html", **ctx)


@fee_bp.route("/remind-all", methods=["POST"])
@fee_staff_required
def remind_all():
    count = send_bulk_reminders(session["school_id"], session["user_id"], status="overdue")
    flash(f"Sent reminders for {count} overdue fee record(s).", "success" if count else "info")
    return redirect(request.referrer or url_for("fees.index"))


@fee_bp.route("/receipt/<fee_id>")
@fee_staff_required
def receipt(fee_id):
    school_id = session["school_id"]
    fee = get_fee_record(fee_id, school_id)
    if not fee:
        abort(404)
    receipt_row = get_receipt_for_fee(fee_id, school_id)
    student = fee.get("student") or {}

    ctx = _ctx("challans")
    ctx.update({
        "fee": fee,
        "receipt": receipt_row,
        "student": student,
        "page_title": f"Receipt {receipt_row['receipt_number'] if receipt_row else ''}",
    })
    return render_template("fees/receipt.html", **ctx)


@fee_bp.route("/receipt/<fee_id>/pdf")
@fee_staff_required
def receipt_pdf(fee_id):
    school_id = session["school_id"]
    fee = get_fee_record(fee_id, school_id)
    if not fee:
        abort(404)
    receipt_row = get_receipt_for_fee(fee_id, school_id)
    if not receipt_row:
        flash("No receipt found. Record a payment first.", "error")
        return redirect(url_for("fees.challan_detail", fee_id=fee_id))

    school = get_school_by_id(school_id)
    student = fee.get("student") or {}
    pdf_bytes = generate_receipt_pdf(school, fee, receipt_row, student)
    filename = f"receipt_{receipt_row['receipt_number']}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
