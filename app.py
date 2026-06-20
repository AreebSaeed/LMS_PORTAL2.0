from flask import Flask, redirect, url_for
from config import Config
from controllers.auth_controller import auth_bp
from controllers.dashboard_controller import dashboard_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
