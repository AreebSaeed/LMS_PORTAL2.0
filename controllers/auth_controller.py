from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.supabase_client import supabase
from models.user_model import get_profile_by_id, resolve_login_email
from controllers.dashboard_controller import ROLE_LABELS

auth_bp = Blueprint("auth", __name__)

LOGIN_ROLES = [(role, label) for role, label in ROLE_LABELS.items()]


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        identifier = request.form.get("login_id", "").strip()
        password = request.form.get("password", "")
        manual_role = request.form.get("manual_role") == "on"
        selected_role = request.form.get("role", "").strip()

        if not identifier or not password:
            flash("Please enter your username/email/ID and password.", "error")
            return render_template(
                "auth/login.html",
                login_roles=LOGIN_ROLES,
                manual_role=manual_role,
                selected_role=selected_role,
                login_id=identifier,
            )

        email = resolve_login_email(identifier)
        if not email:
            flash(
                "Incorrect login details. Please re-enter your credentials.",
                "error",
            )
            return render_template(
                "auth/login.html",
                login_roles=LOGIN_ROLES,
                manual_role=manual_role,
                selected_role=selected_role,
                login_id=identifier,
            )

        try:
            response = supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            user = response.user
            profile = get_profile_by_id(user.id)

            if not profile:
                flash("Account profile not found. Contact your administrator.", "error")
                return render_template(
                    "auth/login.html",
                    login_roles=LOGIN_ROLES,
                    manual_role=manual_role,
                    selected_role=selected_role,
                    login_id=identifier,
                )

            if not profile.get("is_active"):
                flash(
                    "Your account has been deactivated. Contact your administrator.",
                    "error",
                )
                return render_template(
                    "auth/login.html",
                    login_roles=LOGIN_ROLES,
                    manual_role=manual_role,
                    selected_role=selected_role,
                    login_id=identifier,
                )

            actual_role = profile["role"]

            if manual_role:
                if not selected_role:
                    flash("Please select your role or use automatic detection.", "error")
                    return render_template(
                        "auth/login.html",
                        login_roles=LOGIN_ROLES,
                        manual_role=True,
                        selected_role=selected_role,
                        login_id=identifier,
                    )
                if selected_role != actual_role:
                    flash(
                        "The selected role does not match your account. "
                        "Please re-enter your credentials.",
                        "error",
                    )
                    return render_template(
                        "auth/login.html",
                        login_roles=LOGIN_ROLES,
                        manual_role=True,
                        selected_role=selected_role,
                        login_id=identifier,
                    )

            session["user_id"] = user.id
            session["access_token"] = response.session.access_token
            session["role"] = actual_role
            session["full_name"] = profile["full_name"]
            session["school_id"] = profile.get("school_id")

            return redirect(url_for("dashboard.index"))

        except Exception:
            flash(
                "Incorrect login details. Please re-enter your credentials.",
                "error",
            )
            return render_template(
                "auth/login.html",
                login_roles=LOGIN_ROLES,
                manual_role=manual_role,
                selected_role=selected_role,
                login_id=identifier,
            )

    return render_template("auth/login.html", login_roles=LOGIN_ROLES)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
