import os
from flask import Flask, redirect, request, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message = "Войдите, чтобы продолжить"

# Max upload size: 16 MB
MAX_UPLOAD_SIZE = 16 * 1024 * 1024


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    # Ensure instance and uploads folders exist
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = os.path.join(app.instance_path, "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE

    # Database: SQLite file inside instance folder (mounted as volume in Docker)
    db_path = os.path.join(app.instance_path, "crm.sqlite")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    db.init_app(app)
    login_manager.init_app(app)

    # Import models so they are registered
    from app import models  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    with app.app_context():
        db.create_all()

    # Register blueprint
    from app.routes import bp
    app.register_blueprint(bp)

    return app