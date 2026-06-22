from flask import Flask, redirect, url_for
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


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

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

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
