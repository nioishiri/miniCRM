import os
from flask import (
    Blueprint, current_app, flash, redirect,
    render_template, request, send_from_directory, url_for,
)
from werkzeug.utils import secure_filename
from app import db
from app.models import Order, Attachment, Announcement

bp = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {
    # Documents
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "txt", "csv", "rtf", "odt", "ods", "odp",
    # Images
    "jpg", "jpeg", "png", "gif", "webp", "bmp", "svg",
    # Archives
    "zip", "rar", "7z", "tar", "gz",
    # Other
    "json", "xml", "html", "md",
}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_attachments(order: Order) -> None:
    """Save uploaded files from request and attach them to order."""
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    files = request.files.getlist("files")

    for f in files:
        if not f or not f.filename:
            continue

        original = secure_filename(f.filename)
        if not _allowed_file(original):
            flash(f"Пропущен «{original}» — недопустимый тип файла", "warning")
            continue

        stored = Attachment.generate_stored_name(original)
        f.save(os.path.join(upload_folder, stored))

        mime = f.mimetype or "application/octet-stream"
        filepath = os.path.join(upload_folder, stored)
        size = os.path.getsize(filepath) if os.path.exists(filepath) else 0

        attachment = Attachment(
            order=order,
            filename=original,
            stored_name=stored,
            file_size=size,
            mime_type=mime,
        )
        db.session.add(attachment)
        flash(f"Файл «{original}» прикреплён", "success")

    db.session.commit()


def _remove_file(stored_name: str) -> None:
    """Remove a file from disk if it exists."""
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(upload_folder, stored_name)
    if os.path.exists(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# Order list (home page)
# ---------------------------------------------------------------------------
@bp.route("/")
def index():
    status_filter = request.args.get("tab", "").strip()
    query = Order.query.order_by(Order.updated_at.desc())

    if status_filter == "active":
        query = query.filter(Order.status.in_(["new", "in_progress"]))
    elif status_filter == "done":
        query = query.filter_by(status="done")
    elif status_filter == "cancelled":
        query = query.filter_by(status="cancelled")

    orders = query.all()
    return render_template(
        "index.html",
        orders=orders,
        current_tab=status_filter,
        status_choices=Order.STATUS_CHOICES,
    )


# ---------------------------------------------------------------------------
# Create a new order
# ---------------------------------------------------------------------------
@bp.route("/order/new", methods=["GET", "POST"])
def order_create():
    if request.method == "POST":
        customer = request.form.get("customer", "").strip()
        description = request.form.get("description", "").strip()

        if not customer:
            return render_template("order_form.html", error="Имя клиента обязательно")

        order = Order(customer=customer, description=description, status="new")
        db.session.add(order)
        db.session.commit()

        _save_attachments(order)

        flash("Заказ создан!", "success")
        return redirect(url_for("main.order_detail", order_id=order.id))

    return render_template("order_form.html")
# ---------------------------------------------------------------------------
# View a single order
# ---------------------------------------------------------------------------
@bp.route("/order/<int:order_id>")
def order_detail(order_id: int):
    order = db.get_or_404(Order, order_id)
    return render_template("order_detail.html", order=order)


# ---------------------------------------------------------------------------
# Change order status
# ---------------------------------------------------------------------------
@bp.route("/order/<int:order_id>/status", methods=["POST"])
def order_change_status(order_id: int):
    order = db.get_or_404(Order, order_id)
    new_status = request.form.get("status", "").strip()

    valid_statuses = [s[0] for s in Order.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return "Недопустимый статус", 400

    order.status = new_status
    db.session.commit()
    flash(f"Статус изменён на «{order.status_label()}»", "info")
    return redirect(url_for("main.order_detail", order_id=order.id))


# ---------------------------------------------------------------------------
# Delete an order
# ---------------------------------------------------------------------------
@bp.route("/order/<int:order_id>/delete", methods=["POST"])
def order_delete(order_id: int):
    order = db.get_or_404(Order, order_id)

    for att in order.attachments:
        _remove_file(att.stored_name)

    db.session.delete(order)
    db.session.commit()
    flash("Заказ удалён", "secondary")
    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Upload attachment(s) to an existing order
# ---------------------------------------------------------------------------
@bp.route("/order/<int:order_id>/upload", methods=["POST"])
def upload_attachment(order_id: int):
    order = db.get_or_404(Order, order_id)
    _save_attachments(order)
    return redirect(url_for("main.order_detail", order_id=order.id))


# ---------------------------------------------------------------------------
# Download attachment
# ---------------------------------------------------------------------------
@bp.route("/attachment/<int:attachment_id>/download")
def download_attachment(attachment_id: int):
    att = db.get_or_404(Attachment, attachment_id)
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(
        upload_folder, att.stored_name,
        download_name=att.filename,
        as_attachment=True,
    )


# ---------------------------------------------------------------------------
# Delete attachment
# ---------------------------------------------------------------------------
@bp.route("/attachment/<int:attachment_id>/delete", methods=["POST"])
def delete_attachment(attachment_id: int):
    att = db.get_or_404(Attachment, attachment_id)
    order_id = att.order_id
    _remove_file(att.stored_name)
    db.session.delete(att)
    db.session.commit()
    flash(f"Файл «{att.filename}» удалён", "secondary")
    return redirect(url_for("main.order_detail", order_id=order_id))


# ===================================================================
# Board / Announcements
# ===================================================================

@bp.route("/board")
def board_list():
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template("announce_list.html", announcements=announcements)


@bp.route("/board/new", methods=["GET", "POST"])
def announcement_create():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()

        if not title:
            return render_template(
                "announcement_form.html", error="Заголовок обязателен",
                prev_title=title, prev_body=body,
            )

        a = Announcement(title=title, body=body)
        db.session.add(a)
        db.session.commit()
        flash("Объявление опубликовано", "success")
        return redirect(url_for("main.board_list"))

    return render_template("announcement_form.html")


@bp.route("/board/<int:ann_id>/edit", methods=["GET", "POST"])
def announcement_edit(ann_id: int):
    ann = db.get_or_404(Announcement, ann_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()

        if not title:
            return render_template(
                "announcement_form.html", announcement=ann, error="Заголовок обязателен",
                prev_title=title, prev_body=body,
            )

        ann.title = title
        ann.body = body
        db.session.commit()
        flash("Объявление обновлено", "success")
        return redirect(url_for("main.board_list"))

    return render_template("announcement_form.html", announcement=ann)


@bp.route("/board/<int:ann_id>/delete", methods=["POST"])
def announcement_delete(ann_id: int):
    ann = db.get_or_404(Announcement, ann_id)
    db.session.delete(ann)
    db.session.commit()
    flash("Объявление удалено", "secondary")
    return redirect(url_for("main.board_list"))


