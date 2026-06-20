from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.supabase_client import supabase
from models.user_model import get_profile_by_id

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        try:
            response = supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            user = response.user
            profile = get_profile_by_id(user.id)

            if not profile:
                flash("Account profile not found. Contact your administrator.", "error")
                return render_template("auth/login.html")

            if not profile.get("is_active"):
                flash("Your account has been deactivated. Contact your administrator.", "error")
                return render_template("auth/login.html")

            session["user_id"] = user.id
            session["access_token"] = response.session.access_token
            session["role"] = profile["role"]
            session["full_name"] = profile["full_name"]
            session["school_id"] = profile.get("school_id")

            return redirect(url_for("dashboard.index"))

        except Exception:
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
