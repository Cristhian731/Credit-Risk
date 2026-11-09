"""Income and expense routes. Data is read and written through the repository."""
from flask import abort, flash, redirect, render_template, request, url_for

from ..auth.services import get_current_user, login_required
from ..services.repository import (
    delete_transaction,
    get_transaction,
    list_transactions,
    save_transaction,
    update_transaction,
)
from . import bp
from .forms import validate_transaction


def _render_form(form, action, title, status=200):
    """The same form serves creation and edition."""
    return render_template("transactions/form.html", form=form, action=action, title=title), status


def _owned_or_404(transaction_id):
    """The current user's transaction; someone else's id looks exactly like a missing one."""
    transaction = get_transaction(get_current_user().id, transaction_id)
    if transaction is None:
        abort(404)
    return transaction


def _as_form(transaction):
    """A stored transaction as the text values the form shows."""
    return {
        "type": transaction["type"],
        "amount": f"{transaction['amount']:.2f}",
        "date": transaction["date"].isoformat(),
        "category": transaction["category"],
        "description": transaction["description"],
    }


@bp.route("/")
@login_required
def index():
    """List the current user's transactions."""
    user = get_current_user()
    return render_template("transactions/index.html", transactions=list_transactions(user.id))


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    """GET: show the form. POST: validate and save an income or expense."""
    action, title = url_for("transactions.new"), "New transaction"
    if request.method == "GET":
        return _render_form({}, action, title)

    values, errors = validate_transaction(request.form)
    if errors:
        for message in errors:
            flash(message, "danger")
        return _render_form(request.form, action, title, 400)

    values["user_id"] = get_current_user().id
    save_transaction(values)
    flash("Transaction saved.", "success")
    return redirect(url_for("transactions.index"))


@bp.route("/<int:transaction_id>/edit", methods=["GET", "POST"])
@login_required
def edit(transaction_id):
    """GET: show the form filled in. POST: validate exactly like ``new`` and update."""
    transaction = _owned_or_404(transaction_id)
    action, title = url_for("transactions.edit", transaction_id=transaction_id), "Edit transaction"
    if request.method == "GET":
        return _render_form(_as_form(transaction), action, title)

    values, errors = validate_transaction(request.form)
    if errors:
        for message in errors:
            flash(message, "danger")
        return _render_form(request.form, action, title, 400)

    if update_transaction(get_current_user().id, transaction_id, values) is None:
        abort(404)  # deleted in the meantime
    flash("Transaction updated.", "success")
    return redirect(url_for("transactions.index"))


@bp.route("/<int:transaction_id>/delete", methods=["GET", "POST"])
@login_required
def delete(transaction_id):
    """GET: ask for confirmation (nothing is deleted). POST: delete."""
    transaction = _owned_or_404(transaction_id)
    if request.method == "GET":
        return render_template(
            "confirm_delete.html",
            title="Delete transaction",
            details=[
                ("Date", transaction["date"].isoformat()),
                ("Type", transaction["type"].capitalize()),
                ("Category", transaction["category"]),
                ("Description", transaction["description"]),
                ("Amount", "{:,.2f}".format(transaction["amount"])),
            ],
            action=url_for("transactions.delete", transaction_id=transaction_id),
            cancel=url_for("transactions.index"),
        )

    if not delete_transaction(get_current_user().id, transaction_id):
        abort(404)
    flash("Transaction deleted.", "success")
    return redirect(url_for("transactions.index"))
