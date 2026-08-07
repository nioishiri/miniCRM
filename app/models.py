from datetime import datetime, timezone
from app import db


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
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

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
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    def status_badge(self) -> str:
        css = self.STATUS_COLORS.get(self.status, "badge bg-light text-dark")
        return f'<span class="{css}">{self.status_label()}</span>'

    def __repr__(self) -> str:
        return f"<Order #{self.id} [{self.status}]>"