"""Controller: HTTP routes. Business logic lives in services/ and forms.py."""
from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)

from .forms import validate_form

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Landing page."""
    return render_template("index.html")


@main_bp.route("/predict", methods=["GET", "POST"])
def predict():
    """GET: show the customer form. POST: validate, predict, redirect to /result."""
    if request.method == "GET":
        return render_template("predict.html", form={})

    values, errors = validate_form(request.form)
    if errors:
        for message in errors:
            flash(message, "danger")
        # Re-render with the submitted data so the user does not retype everything.
        return render_template("predict.html", form=request.form), 400

    service = current_app.extensions["prediction_service"]
    try:
        session["result"] = service.predict(values)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return render_template("predict.html", form=request.form), 503

    # Post/Redirect/Get avoids duplicate submissions on page refresh.
    return redirect(url_for("main.result"))


@main_bp.route("/result")
def result():
    """Shows the last prediction stored in the session."""
    data = session.get("result")
    if data is None:
        flash("Please submit the form first.", "warning")
        return redirect(url_for("main.predict"))
    return render_template("result.html", result=data)
