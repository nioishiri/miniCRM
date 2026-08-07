import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # Database: SQLite file inside instance folder (mounted as volume in Docker)
    db_path = os.path.join(app.instance_path, "crm.sqlite")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    db.init_app(app)

    # Import models so they are registered
    from app import models  # noqa: F401

    with app.app_context():
        db.create_all()

    # Register blueprint
    from app.routes import bp
    app.register_blueprint(bp)

    return app