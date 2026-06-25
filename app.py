from flask import Flask, redirect, url_for, session, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import traceback
from typing import Optional

from config import Config

_startup_error: Optional[str] = None


def create_app():
    from controllers.auth_controller import auth_bp
    from controllers.dashboard_controller import dashboard_bp
    from controllers.student_controller import student_bp
    from controllers.parent_controller import parent_bp
    from controllers.teacher_controller import teacher_bp
    from controllers.attendance_controller import attendance_bp
    from controllers.parent_portal_controller import parent_portal_bp
    from controllers.teacher_portal_controller import teacher_portal_bp
    from controllers.student_portal_controller import student_portal_bp
    from controllers.exam_controller import exam_bp
    from controllers.fee_controller import fee_bp
    from controllers.announcement_controller import announcement_bp
    from controllers.class_controller import class_bp
    from controllers.timetable_controller import timetable_bp
    from controllers.student_message_controller import student_message_bp

    app = Flask(__name__)
    app.config.from_object(Config)

    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
        )
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    @app.context_processor
    def inject_announcement_bell():
        from models.announcement_model import announcements_list_url_for_role
        if session.get("user_id") and session.get("school_id"):
            role = session.get("role", "")
            return {
                "show_announcement_bell": role in (
                    "school_admin", "accountant", "teacher", "student", "parent"
                ),
                "announcement_bell_list_url": announcements_list_url_for_role(role)
                if role else "",
            }
        return {"show_announcement_bell": False, "announcement_bell_list_url": ""}

    @app.context_processor
    def inject_staff_message_badge():
        from models.student_message_model import count_unread_student_message_notifications
        from models.parent_message_model import count_unread_parent_message_notifications
        if session.get("user_id") and session.get("school_id"):
            role = session.get("role", "")
            try:
                if role == "school_admin":
                    uid = session["user_id"]
                    sid = session["school_id"]
                    return {
                        "unread_student_messages": count_unread_student_message_notifications(uid, sid),
                        "unread_parent_messages": count_unread_parent_message_notifications(uid, sid),
                    }
                if role == "teacher":
                    return {
                        "unread_student_messages": count_unread_student_message_notifications(
                            session["user_id"], session["school_id"]
                        ),
                        "unread_parent_messages": 0,
                    }
            except Exception:
                pass
        return {"unread_student_messages": 0, "unread_parent_messages": 0}

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(student_bp, url_prefix="/students")
    app.register_blueprint(parent_bp, url_prefix="/parents")
    app.register_blueprint(teacher_bp, url_prefix="/teachers")
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    app.register_blueprint(parent_portal_bp, url_prefix="/portal")
    app.register_blueprint(teacher_portal_bp, url_prefix="/teach")
    app.register_blueprint(student_portal_bp, url_prefix="/learn")
    app.register_blueprint(exam_bp, url_prefix="/exams")
    app.register_blueprint(fee_bp, url_prefix="/fees")
    app.register_blueprint(announcement_bp, url_prefix="/announcements")
    app.register_blueprint(class_bp, url_prefix="/classes")
    app.register_blueprint(timetable_bp, url_prefix="/timetable")
    app.register_blueprint(student_message_bp, url_prefix="/messages")

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.route("/api/health")
    def health():
        from models.supabase_client import config_error, supabase_admin
        err = config_error()
        if err:
            return jsonify({"status": "error", "message": err}), 503
        try:
            supabase_admin.table("schools").select("id").limit(1).execute()
            return jsonify({"status": "ok"})
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 503

    return app


def _create_fallback_app(error_text: str) -> Flask:
    fallback = Flask(__name__)

    @fallback.route("/api/health")
    def health_failed():
        return jsonify({
            "status": "startup_failed",
            "message": "The Flask app failed to load. See detail for the traceback.",
            "detail": error_text,
        }), 503

    @fallback.route("/", defaults={"path": ""})
    @fallback.route("/<path:path>")
    def unavailable(path):
        if path == "api/health":
            return health_failed()
        return (
            "<h1>App failed to start</h1>"
            "<p>Open <a href='/api/health'>/api/health</a> to see the error detail.</p>"
            "<p>Usually this means missing Vercel environment variables or a bad dependency.</p>",
            503,
            {"Content-Type": "text/html"},
        )

    return fallback


try:
    app = create_app()
except Exception:
    _startup_error = traceback.format_exc()
    app = _create_fallback_app(_startup_error)


if __name__ == "__main__":
    if _startup_error:
        print(_startup_error)
    else:
        app.run(debug=True)
