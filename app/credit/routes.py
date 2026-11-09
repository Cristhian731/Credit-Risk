"""Credit evaluation routes: customer form and prediction result."""
from flask import abort, flash, redirect, render_template, request, session, url_for

from ..auth.services import get_current_user, login_required
from ..services.repository import (
    delete_credit_application,
    get_credit_application,
    list_credit_applications,
    save_credit_application,
)
from . import bp
from .forms import CHOICE_FIELDS, FIELD_ORDER, NUMERIC_FIELDS, to_record, validate_client, validate_form
from .services import get_predictor

RESULT_SESSION_KEY = "credit_result"
HISTORY_LIMIT = 100


def _render_form(form, status=200):
    return render_template(
        "credit/index.html",
        form=form,
        field_order=FIELD_ORDER,
        numeric_fields=NUMERIC_FIELDS,
        choice_fields=CHOICE_FIELDS,
    ), status


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    """GET: show the customer form. POST: validate, predict, save and show the result."""
    if request.method == "GET":
        return _render_form({})

    client, client_errors = validate_client(request.form)
    values, errors = validate_form(request.form)
    errors = client_errors + errors
    if errors:
        for message in errors:
            flash(message, "danger")
        # Re-render with the submitted data so the user does not retype everything.
        return _render_form(request.form, 400)

    try:
        result = get_predictor().predict(values)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return _render_form(request.form, 503)

    save_credit_application({
        **to_record(values),
        **client,
        "risk_label": result["label"],
        "risk_percent": result["risk_percent"],
        "user_id": get_current_user().id,
    })
    session[RESULT_SESSION_KEY] = result

    # Post/Redirect/Get avoids duplicate submissions on page refresh.
    return redirect(url_for("credit.result"))


@bp.route("/history")
@login_required
def history():
    """List the current user's past evaluations, newest first."""
    user = get_current_user()
    return render_template(
        "credit/history.html",
        applications=list_credit_applications(user.id, limit=HISTORY_LIMIT),
        limit=HISTORY_LIMIT,
    )


@bp.route("/history/<int:application_id>/delete", methods=["GET", "POST"])
@login_required
def delete(application_id):
    """GET: ask for confirmation (nothing is deleted). POST: delete.

    Evaluations are never edited. Someone else's id answers 404, like a missing one.
    """
    user_id = get_current_user().id
    application = get_credit_application(user_id, application_id)
    if application is None:
        abort(404)
    if request.method == "GET":
        return render_template(
            "confirm_delete.html",
            title="Delete evaluation",
            details=[
                ("Date (UTC)", application["created_at"].strftime("%Y-%m-%d %H:%M")),
                ("Customer", application["client_full_name"]),
                ("Document", application["client_document"]),
                ("Loan amount", "{:,.2f}".format(application["loan_amount"])),
                ("Result", f"{application['risk_label']} ({application['risk_percent']}%)"),
            ],
            action=url_for("credit.delete", application_id=application_id),
            cancel=url_for("credit.history"),
        )

    if not delete_credit_application(user_id, application_id):
        abort(404)
    flash("Evaluation deleted.", "success")
    return redirect(url_for("credit.history"))


@bp.route("/result")
@login_required
def result():
    """Show the last prediction stored in the session."""
    data = session.get(RESULT_SESSION_KEY)
    if data is None:
        flash("Please submit the form first.", "info")
        return redirect(url_for("credit.index"))
    return render_template("credit/result.html", result=data)
