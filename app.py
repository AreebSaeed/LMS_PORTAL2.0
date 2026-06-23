from flask import Flask, redirect, url_for, session
from config import Config
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
from models.announcement_model import announcements_list_url_for_role
from models.student_message_model import count_unread_student_message_notifications


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.context_processor
    def inject_announcement_bell():
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
        if session.get("user_id") and session.get("school_id"):
            role = session.get("role", "")
            if role in ("school_admin", "teacher"):
                return {
                    "unread_student_messages": count_unread_student_message_notifications(
                        session["user_id"], session["school_id"]
                    ),
                }
        return {"unread_student_messages": 0}

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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
