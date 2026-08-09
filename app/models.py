from datetime import datetime, timezone
import os
import uuid
import random
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(200), nullable=False, default="")
    role = db.Column(db.String(20), nullable=False, default="user")
    is_active_user = db.Column(db.Boolean, nullable=False, default=True)
    color = db.Column(db.String(7), nullable=False, default="#6C757D")  # Hex color
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    orders = db.relationship("Order", back_populates="creator", lazy="dynamic", order_by="Order.created_at.desc()")
    announcements = db.relationship("Announcement", back_populates="creator", lazy="dynamic", order_by="Announcement.created_at.desc()")

    def set_password(self, pwd: str) -> None:
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd: str) -> bool:
        return check_password_hash(self.password_hash, pwd)

    @property
    def name_or_username(self) -> str:
        return self.display_name or self.username

    @staticmethod
    def generate_random_color() -> str:
        """Generate a random hex color for user badge."""
        colors = [
            "#4A90D9", "#50C878", "#FF6B6B", "#FFA07A", "#9B59B6",
            "#3498DB", "#E74C3C", "#2ECC71", "#F39C12", "#1ABC9C",
            "#9B59B6", "#34495E", "#16A085", "#C0392B", "#8E44AD",
            "#2980B9", "#27AE60", "#D35400", "#7F8C8D", "#E67E22",
        ]
        return random.choice(colors)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    customer = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(
        db.String(20),
        nullable=False,
        default="new",
    )
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    attachments = db.relationship(
        "Attachment", back_populates="order",
        cascade="all, delete-orphan", order_by="Attachment.uploaded_at"
    )
    creator = db.relationship("User", back_populates="orders")

    STATUS_CHOICES = [
        ("new", "Новый"),
        ("in_progress", "В работе"),
        ("done", "Выполнен"),
        ("cancelled", "Отменён"),
    ]

    STATUS_COLORS = {
        "new":        "badge bg-primary",
        "in_progress": "badge bg-warning text-dark",
        "done":       "badge bg-success",
        "cancelled":  "badge bg-secondary",
    }

    def status_label(self) -> str:
        """Get status label from database or fallback to system choices."""
        status = OrderStatus.query.filter_by(slug=self.status, is_active=True).first()
        if status:
            return status.label
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    def status_badge(self) -> str:
        """Get status badge HTML from database or fallback."""
        status = OrderStatus.query.filter_by(slug=self.status, is_active=True).first()
        if status:
            return f'<span class="badge {status.color}">{status.label}</span>'
        css = self.STATUS_COLORS.get(self.status, "badge bg-light text-dark")
        return f'<span class="{css}">{self.status_label()}</span>'

    def __repr__(self) -> str:
        return f"<Order #{self.id} [{self.status}]>"


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    filename = db.Column(db.String(500), nullable=False)       # original name
    stored_name = db.Column(db.String(500), nullable=False)    # UUID on disk
    file_size = db.Column(db.Integer, nullable=False, default=0)
    mime_type = db.Column(db.String(200), nullable=False, default="application/octet-stream")
    uploaded_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    order = db.relationship("Order", back_populates="attachments")

    @staticmethod
    def generate_stored_name(original_filename: str) -> str:
        ext = os.path.splitext(original_filename)[1]
        return f"{uuid.uuid4().hex}{ext}"

    @property
    def is_image(self) -> bool:
        return self.mime_type.startswith("image/")

    @property
    def icon_class(self) -> str:
        """Return a Bootstrap icon class based on file type."""
        mt = self.mime_type
        if mt.startswith("image/"):
            return "bi-file-image"
        if mt == "application/pdf":
            return "bi-file-pdf"
        if "word" in mt or "document" in mt:
            return "bi-file-word"
        if "spreadsheet" in mt or "excel" in mt:
            return "bi-file-excel"
        if mt.startswith("text/"):
            return "bi-file-text"
        if mt.startswith("video/"):
            return "bi-file-play"
        if "zip" in mt or "rar" in mt or "tar" in mt:
            return "bi-file-zip"
        return "bi-file-earmark"

    @staticmethod
    def format_size(size_bytes: int) -> str:
        for unit in ("Б", "КБ", "МБ", "ГБ"):
            if size_bytes < 1024:
                return f"{size_bytes:.0f} {unit}" if unit == "Б" else f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} ТБ"

    def __repr__(self) -> str:
        return f"<Attachment {self.filename}>"


# ===================================================================
# Board / Announcements
# ===================================================================

class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=False, default="")
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    creator = db.relationship("User", back_populates="announcements")

    def formatted_body(self) -> str:
        """Render simple line-break paragraphs."""
        return "<br>".join(f"<p>{p.strip()}</p>" for p in self.body.split("\n") if p.strip())

    def short_preview(self, max_len: int = 120) -> str:
        text = " ".join(self.body.split())
        if len(text) > max_len:
            return text[:max_len].rsplit(" ", 1)[0] + "…"
        return text

    def __repr__(self) -> str:
        return f"<Announcement #{self.id}: {self.title}>"


# ===================================================================
# Order Statuses (customizable)
# ===================================================================

class OrderStatus(db.Model):
    __tablename__ = "order_statuses"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    label = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(100), nullable=False, default="bg-primary")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_system = db.Column(db.Boolean, nullable=False, default=False)

    @staticmethod
    def get_all_active():
        """Get all active statuses ordered by sort_order."""
        return OrderStatus.query.filter_by(is_active=True).order_by(OrderStatus.sort_order).all()

    @staticmethod
    def get_all():
        """Get all statuses ordered by sort_order."""
        return OrderStatus.query.order_by(OrderStatus.sort_order).all()

    def __repr__(self) -> str:
        return f"<OrderStatus {self.slug}: {self.label}>"