import os
import sqlite3
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message = "Войдите, чтобы продолжить"

# Max upload size: 16 MB
MAX_UPLOAD_SIZE = 16 * 1024 * 1024


def _migrate_db(db_path: str) -> None:
    """Add missing columns to existing tables (safe for new DBs too)."""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Get existing columns for each table
        for table, col_specs in [
            ("orders",         [("creator_id", "INTEGER")]),
            ("announcements",  [("creator_id", "INTEGER")]),
            ("users",          [("color", "TEXT")]),
        ]:
            cur.execute(f"PRAGMA table_info({table})")
            existing_cols = {row[1] for row in cur.fetchall()}
            for col_name, col_type in col_specs:
                if col_name not in existing_cols:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                    print(f"[migrate] Added {table}.{col_name}")

        # Create order_statuses table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_statuses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                label TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT 'bg-primary',
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_system INTEGER NOT NULL DEFAULT 0
            )
        """)
        print("[migrate] Created order_statuses table")

        # Insert default system statuses if table is empty
        cur.execute("SELECT COUNT(*) FROM order_statuses")
        if cur.fetchone()[0] == 0:
            default_statuses = [
                ("new", "Новый", "bg-primary", 0, 1, 1),
                ("in_progress", "В работе", "bg-warning text-dark", 1, 1, 1),
                ("done", "Выполнен", "bg-success", 2, 1, 1),
                ("cancelled", "Отменён", "bg-secondary", 3, 1, 1),
            ]
            cur.executemany(
                "INSERT INTO order_statuses (slug, label, color, sort_order, is_active, is_system) VALUES (?, ?, ?, ?, ?, ?)",
                default_statuses
            )
            print("[migrate] Inserted default statuses")

        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        # DB file doesn't exist yet — perfectly fine
        pass


def _ensure_admin() -> None:
    """Create a default admin user if no users exist."""
    # Avoid circular import
    from app.models import User  # noqa: F811
    if User.query.count() == 0:
        admin = User(username="admin", display_name="Admin", role="admin")
        admin.set_password("admin")
        db.session.add(admin)
        db.session.commit()
        print("[auth] Default admin created: admin / admin")


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
        _migrate_db(db_path)
        _ensure_admin()

    # Register blueprint
    from app.routes import bp
    app.register_blueprint(bp)

    return app