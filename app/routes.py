from flask import Blueprint, redirect, render_template, request, url_for
from app import db
from app.models import Order

bp = Blueprint("main", __name__)


# ---------------------------------------------------------------------------
# Order list (home page)
# ---------------------------------------------------------------------------
@bp.route("/")
def index():
    status_filter = request.args.get("status", "").strip()
    query = Order.query.order_by(Order.updated_at.desc())

    if status_filter:
        query = query.filter_by(status=status_filter)

    orders = query.all()
    return render_template(
        "index.html",
        orders=orders,
        status_filter=status_filter,
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
    return redirect(url_for("main.order_detail", order_id=order.id))


# ---------------------------------------------------------------------------
# Delete an order
# ---------------------------------------------------------------------------
@bp.route("/order/<int:order_id>/delete", methods=["POST"])
def order_delete(order_id: int):
    order = db.get_or_404(Order, order_id)
    db.session.delete(order)
    db.session.commit()
    return redirect(url_for("main.index"))