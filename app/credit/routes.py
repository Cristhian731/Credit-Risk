"""Credit evaluation routes: customer form, prediction result and model pages."""
from flask import abort, current_app, flash, redirect, render_template, request, url_for

from ..auth.services import get_current_user, login_required
from ..services.repository import (
    delete_credit_application,
    get_credit_application,
    paginate_credit_applications,
    save_credit_application,
)
from . import bp
from .forms import CHOICE_FIELDS, FIELD_ORDER, NUMERIC_FIELDS, to_record, validate_client, validate_form
from ml.schemas import MODEL_NAMES

from .services import RECOMMENDATIONS, get_predictor, get_registry


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

    saved = save_credit_application({
        **to_record(values),
        **client,
        "risk_label": result["label"],
        "risk_percent": result["risk_percent"],
        "user_id": get_current_user().id,
    })
    # Post/Redirect/Get: reloading the result page never submits the form again.
    return redirect(url_for("credit.result", application_id=saved["id"]))


@bp.route("/history")
@login_required
def history():
    """List the current user's past evaluations, newest first, one page (?page=N) at a time."""
    page = paginate_credit_applications(
        get_current_user().id,
        request.args.get("page", 1, type=int),
        current_app.config["PAGE_SIZE"],
    )
    return render_template("credit/history.html", applications=page["items"], pagination=page)


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
def result_without_id():
    """Old address without an id: the results now live in the history."""
    return redirect(url_for("credit.history"))


@bp.route("/result/<int:application_id>")
@login_required
def result(application_id):
    """Show a saved evaluation, loaded from the database by id and owner.

    Someone else's or a deleted evaluation answers 404. The recommendation is
    derived from the stored label when the page is read, not stored.
    """
    application = get_credit_application(get_current_user().id, application_id)
    if application is None:
        abort(404)
    result = {
        "label": application["risk_label"],
        "risk_percent": application["risk_percent"],
        "recommendation": RECOMMENDATIONS[application["risk_label"]],
    }
    return render_template("credit/result.html", result=result, application=application)


@bp.route("/models/")
@login_required
def models():
    """Compare the three candidate models (example data until real artifacts exist)."""
    return render_template("credit/models.html", catalog=get_registry().catalog())


@bp.route("/models/<name>/")
@login_required
def model_detail(name):
    """Metrics of one model. Names outside ml.schemas.MODEL_NAMES answer 404."""
    if name not in MODEL_NAMES:
        abort(404)
    catalog = get_registry().catalog()
    if name not in catalog["metrics"]:
        abort(404)
    return render_template(
        "credit/model_detail.html",
        catalog=catalog,
        metrics=catalog["metrics"][name],
        is_champion=catalog["manifest"]["champion"] == name,
    )
