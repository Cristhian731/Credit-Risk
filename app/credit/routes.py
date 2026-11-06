"""Credit evaluation routes: customer form and prediction result."""
from flask import flash, redirect, render_template, request, session, url_for

from ..auth.services import get_current_user, login_required
from ..services.repository import save_credit_application
from . import bp
from .forms import CHOICE_FIELDS, FIELD_ORDER, NUMERIC_FIELDS, to_record, validate_form
from .services import get_predictor

RESULT_SESSION_KEY = "credit_result"


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

    values, errors = validate_form(request.form)
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
        "risk_label": result["label"],
        "risk_percent": result["risk_percent"],
        # The form does not identify the client yet (see docs/INTEGRATION.md).
        "client_id": None,
        # INTEGRATION: user_id comes from authenticated user
        "user_id": get_current_user().id,
    })
    session[RESULT_SESSION_KEY] = result

    # Post/Redirect/Get avoids duplicate submissions on page refresh.
    return redirect(url_for("credit.result"))


@bp.route("/result")
@login_required
def result():
    """Show the last prediction stored in the session."""
    data = session.get(RESULT_SESSION_KEY)
    if data is None:
        flash("Please submit the form first.", "info")
        return redirect(url_for("credit.index"))
    return render_template("credit/result.html", result=data)
