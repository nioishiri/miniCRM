import os
import re
import mimetypes
from flask import (
    Blueprint, current_app, flash, redirect,
    render_template, request, send_from_directory, url_for,
)
from flask_login import login_required, current_user, login_user, logout_user
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename
from app import db
from app.models import Order, Attachment, Announcement, User, OrderStatus

bp = Blueprint("main", __name__)


def admin_required(f):
    """Decorator: redirects non-admin users."""
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != "admin":
            return "Forbidden", 403
        return f(*args, **kwargs)
    return decorated

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


def _save_attachments(order: Order | None = None, announcement: Announcement | None = None) -> None:
    """Save uploaded files from request and attach them to an order or announcement."""
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
        filepath = os.path.join(upload_folder, stored)
        f.save(filepath)

        mime = f.mimetype or mimetypes.guess_type(original)[0] or "application/octet-stream"
        size = os.path.getsize(filepath) if os.path.exists(filepath) else 0

        attachment = Attachment(
            filename=original,
            stored_name=stored,
            file_size=size,
            mime_type=mime,
        )
        if order is not None:
            attachment.order = order
        if announcement is not None:
            attachment.announcement = announcement
        db.session.add(attachment)
        flash(f"Файл «{original}» прикреплён", "success")

    db.session.commit()


def _remove_file(stored_name: str) -> None:
    """Remove a file from disk if it exists."""
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(upload_folder, stored_name)
    if os.path.exists(path):
        os.remove(path)




# ===================================================================
# Auth helpers
# ===================================================================

@bp.before_request
def require_auth():
    if request.endpoint == "main.login":
        return
    if not current_user.is_authenticated:
        return redirect(url_for("main.login", next=request.full_path))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash("Неверный логин или пароль", "danger")
            return render_template("login.html", error=True)
        if not user.is_active_user:
            flash("Аккаунт заблокирован", "warning")
            return render_template("login.html", error=True)
        login_user(user)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("main.index"))
    return render_template("login.html")


@bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.login"))


# ---------------------------------------------------------------------------
# Order list (home page)
# ---------------------------------------------------------------------------
@login_required
@bp.route("/")
def index():
    status_filter = request.args.get("tab", "").strip()
    query = Order.query.options(joinedload(Order.creator)).order_by(Order.updated_at.desc())

    if status_filter == "active":
        # Active = everything except done/cancelled (includes custom statuses)
        query = query.filter(Order.status.notin_(["done", "cancelled"]))
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
@login_required
@bp.route("/order/new", methods=["GET", "POST"])
def order_create():
    if request.method == "POST":
        customer = request.form.get("customer", "").strip()
        description = request.form.get("description", "").strip()

        if not customer:
            return render_template("order_form.html", error="Имя клиента обязательно")

        order = Order(customer=customer, description=description, status="new", creator_id=current_user.id)
        db.session.add(order)
        db.session.commit()

        _save_attachments(order)

        flash("Заказ создан!", "success")
        return redirect(url_for("main.order_detail", order_id=order.id))

    return render_template("order_form.html")
# ---------------------------------------------------------------------------
# View a single order
# ---------------------------------------------------------------------------
@login_required
@bp.route("/order/<int:order_id>")
def order_detail(order_id: int):
    order = db.get_or_404(Order, order_id)
    statuses = OrderStatus.get_all_active()
    return render_template("order_detail.html", order=order, order_statuses=statuses)


# ---------------------------------------------------------------------------
# Change order status
# ---------------------------------------------------------------------------
@login_required
@bp.route("/order/<int:order_id>/status", methods=["POST"])
def order_change_status(order_id: int):
    order = db.get_or_404(Order, order_id)
    new_status = request.form.get("status", "").strip()

    # Validate against active statuses from database
    valid_statuses = [s.slug for s in OrderStatus.get_all_active()]
    if new_status not in valid_statuses:
        return "Недопустимый статус", 400

    order.status = new_status
    db.session.commit()
    flash(f"Статус изменён на «{order.status_label()}»", "info")
    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Delete an order
# ---------------------------------------------------------------------------
@login_required
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
@login_required
@bp.route("/order/<int:order_id>/upload", methods=["POST"])
def upload_attachment(order_id: int):
    order = db.get_or_404(Order, order_id)
    _save_attachments(order)
    return redirect(url_for("main.order_detail", order_id=order.id))


# ---------------------------------------------------------------------------
# Download attachment
# ---------------------------------------------------------------------------
@login_required
@bp.route("/attachment/<int:attachment_id>/download")
def download_attachment(attachment_id: int):
    att = db.get_or_404(Attachment, attachment_id)
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    force_download = request.args.get("download") == "1"
    return send_from_directory(
        upload_folder, att.stored_name,
        download_name=att.filename,
        as_attachment=force_download,
    )


# ---------------------------------------------------------------------------
# Delete attachment
# ---------------------------------------------------------------------------
@login_required
@bp.route("/attachment/<int:attachment_id>/delete", methods=["POST"])
def delete_attachment(attachment_id: int):
    att = db.get_or_404(Attachment, attachment_id)
    order_id = att.order_id
    _remove_file(att.stored_name)
    db.session.delete(att)
    db.session.commit()
    flash(f"Файл «{att.filename}» удалён", "secondary")
    if order_id:
        return redirect(url_for("main.order_detail", order_id=order_id))
    return redirect(url_for("main.board_list"))


# ===================================================================
# Board / Announcements
# ===================================================================

@login_required
@bp.route("/board")
def board_list():
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template("announce_list.html", announcements=announcements)


@login_required
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

        a = Announcement(title=title, body=body, creator_id=current_user.id)
        db.session.add(a)
        db.session.commit()
        _save_attachments(announcement=a)
        flash("Объявление опубликовано", "success")
        return redirect(url_for("main.board_list"))

    return render_template("announcement_form.html")


@login_required
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
        _save_attachments(announcement=ann)
        flash("Объявление обновлено", "success")
        return redirect(url_for("main.board_list"))

    return render_template("announcement_form.html", announcement=ann)


@login_required
@bp.route("/board/<int:ann_id>/delete", methods=["POST"])
def announcement_delete(ann_id: int):
    ann = db.get_or_404(Announcement, ann_id)
    for att in ann.attachments:
        _remove_file(att.stored_name)
    db.session.delete(ann)
    db.session.commit()
    flash("Объявление удалено", "secondary")
    return redirect(url_for("main.board_list"))



# ===================================================================
# Admin panel
# ===================================================================

@login_required
@admin_required
@bp.route("/admin/users")
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", users=users)


@login_required
@admin_required
@bp.route("/admin/users", methods=["POST"])
def admin_create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    display = request.form.get("display_name", "").strip()
    role = request.form.get("role", "user")

    if not username or not password:
        flash("Логин и пароль обязательны", "danger")
        return redirect(url_for("main.admin_users"))

    if User.query.filter_by(username=username).first():
        flash(f"Пользователь «{username}» уже существует", "danger")
        return redirect(url_for("main.admin_users"))

    u = User(username=username, display_name=display or username, role=role)
    u.set_password(password)
    u.color = User.generate_random_color()
    db.session.add(u)
    db.session.commit()
    flash(f"Пользователь «{username}» создан", "success")
    return redirect(url_for("main.admin_users"))


@login_required
@admin_required
@bp.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
def admin_toggle_user(user_id: int):
    u = db.get_or_404(User, user_id)
    if u.id == current_user.id:
        flash("Нельзя заблокировать самого себя", "warning")
        return redirect(url_for("main.admin_users"))
    u.is_active_user = not u.is_active_user
    db.session.commit()
    status = "разблокирован" if u.is_active_user else "заблокирован"
    flash(f"Пользователь «{u.username}» {status}", "info")
    return redirect(url_for("main.admin_users"))


@login_required
@admin_required
@bp.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])
def admin_reset_password(user_id: int):
    u = db.get_or_404(User, user_id)
    new_pwd = request.form.get("password", "")
    if not new_pwd:
        flash("Пароль не может быть пустым", "danger")
        return redirect(url_for("main.admin_users"))
    u.set_password(new_pwd)
    db.session.commit()
    flash(f"Пароль пользователя «{u.username}» изменён", "info")
    return redirect(url_for("main.admin_users"))


# ===================================================================
# Custom Statuses Management (Admin only)
# ===================================================================

@login_required
@admin_required
@bp.route("/admin/statuses", methods=["GET", "POST"])
def admin_statuses():
    ALLOWED_COLORS = {
        "bg-primary", "bg-success", "bg-warning text-dark",
        "bg-danger", "bg-info", "bg-secondary", "bg-dark",
    }

    if request.method == "POST":
        slug = request.form.get("slug", "").strip().lower().replace(" ", "_")
        label = request.form.get("label", "").strip()
        color = request.form.get("color", "bg-primary").strip()

        if not slug or not label:
            flash("Slug и название обязательны", "danger")
            return redirect(url_for("main.admin_statuses"))

        if not re.fullmatch(r"[a-z0-9_]+", slug):
            flash("Slug может содержать только латинские буквы, цифры и _", "danger")
            return redirect(url_for("main.admin_statuses"))

        if color not in ALLOWED_COLORS:
            color = "bg-primary"

        if OrderStatus.query.filter_by(slug=slug).first():
            flash(f"Статус «{slug}» уже существует", "danger")
            return redirect(url_for("main.admin_statuses"))

        max_order = db.session.query(db.func.max(OrderStatus.sort_order)).scalar() or 0
        status = OrderStatus(slug=slug, label=label, color=color, sort_order=max_order + 1)
        db.session.add(status)
        try:
            db.session.commit()
            flash(f"Статус «{label}» создан", "success")
        except Exception:
            db.session.rollback()
            flash("Ошибка при создании статуса. Проверьте лог сервера.", "danger")
        return redirect(url_for("main.admin_statuses"))

    statuses = OrderStatus.get_all()
    return render_template("admin_statuses.html", statuses=statuses)


@login_required
@admin_required
@bp.route("/admin/statuses/<int:status_id>/edit", methods=["POST"])
def admin_edit_status(status_id: int):
    ALLOWED_COLORS = {
        "bg-primary", "bg-success", "bg-warning text-dark",
        "bg-danger", "bg-info", "bg-secondary", "bg-dark",
    }

    status = db.get_or_404(OrderStatus, status_id)
    label = request.form.get("label", "").strip()
    color = request.form.get("color", "bg-primary").strip()
    is_active = request.form.get("is_active") == "on"

    if not label:
        flash("Название обязательно", "danger")
        return redirect(url_for("main.admin_statuses"))

    if color not in ALLOWED_COLORS:
        color = "bg-primary"

    status.label = label
    status.color = color
    # System statuses cannot be deactivated (disabled checkbox sends nothing)
    if not status.is_system:
        status.is_active = is_active
    try:
        db.session.commit()
        flash(f"Статус «{label}» обновлён", "success")
    except Exception:
        db.session.rollback()
        flash("Ошибка при обновлении статуса", "danger")
    return redirect(url_for("main.admin_statuses"))


@login_required
@admin_required
@bp.route("/admin/statuses/<int:status_id>/delete", methods=["POST"])
def admin_delete_status(status_id: int):
    status = db.get_or_404(OrderStatus, status_id)

    if status.is_system:
        flash("Системные статусы нельзя удалить", "warning")
        return redirect(url_for("main.admin_statuses"))

    # Check if any orders use this status
    orders_count = Order.query.filter_by(status=status.slug).count()
    if orders_count > 0:
        flash(f"Нельзя удалить: {orders_count} заказов используют этот статус", "danger")
        return redirect(url_for("main.admin_statuses"))

    db.session.delete(status)
    db.session.commit()
    flash(f"Статус «{status.label}» удалён", "secondary")
    return redirect(url_for("main.admin_statuses"))


# ===================================================================
# User Profile (change password)
# ===================================================================

@login_required
@bp.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Текущий пароль неверный", "danger")
            return redirect(url_for("main.profile"))

        if len(new_password) < 6:
            flash("Новый пароль должен содержать минимум 6 символов", "danger")
            return redirect(url_for("main.profile"))

        if new_password != confirm_password:
            flash("Новые пароли не совпадают", "danger")
            return redirect(url_for("main.profile"))

        current_user.set_password(new_password)
        db.session.commit()
        flash("Пароль успешно изменён", "success")
        return redirect(url_for("main.profile"))

    return render_template("profile.html")
