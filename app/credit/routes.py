"""Credit evaluation routes: customer form and prediction result."""
from flask import flash, redirect, render_template, request, session, url_for

from ..auth.services import login_required
from . import bp
from .forms import CHOICE_FIELDS, FIELD_ORDER, NUMERIC_FIELDS, validate_form
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
    """GET: show the customer form. POST: validate, predict and redirect to the result."""
    if request.method == "GET":
        return _render_form({})

    values, errors = validate_form(request.form)
    if errors:
        for message in errors:
            flash(message, "danger")
        # Re-render with the submitted data so the user does not retype everything.
        return _render_form(request.form, 400)

    try:
        session[RESULT_SESSION_KEY] = get_predictor().predict(values)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return _render_form(request.form, 503)

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
