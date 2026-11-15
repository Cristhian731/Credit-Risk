"""Credit evaluation routes: customer form, prediction result and model pages."""
from flask import abort, current_app, flash, redirect, render_template, request, url_for

from ..auth.services import get_current_user, roles_required
from ..services import rules
from ..services.repository import (
    delete_credit_application,
    finance_summary_for_credit,
    get_credit_application,
    paginate_credit_applications,
    save_credit_application,
    update_credit_application,
    user_client,
    withdraw_credit_application,
)
from . import bp
from .forms import CHOICE_FIELDS, FIELD_ORDER, NUMERIC_FIELDS, to_record, validate_client, validate_form
from ml.schemas import CHAMPION_AUC_MARGIN, DISPLAY_NAMES, MODEL_NAMES, parse_model_version_tag

from .services import RECOMMENDATIONS, get_registry, scored_prediction


def _with_client(form):
    """The form values with the name and document of the applicant prefilled (first request: empty)."""
    values = dict(form)
    client = user_client(get_current_user().id)
    if client:
        values.setdefault("client_full_name", client["full_name"])
        values.setdefault("client_document", client["document"])
    return values


def _render_form(form, status=200, edit_id=None):
    return render_template(
        "credit/index.html",
        form=_with_client(form),
        edit_id=edit_id,
        field_order=FIELD_ORDER,
        numeric_fields=NUMERIC_FIELDS,
        choice_fields=CHOICE_FIELDS,
    ), status


def _finance_origin(summary):
    """Where each prefilled value comes from, for the notes under the form fields."""
    origin = {}
    count = len(summary["months"])
    if summary["monthly_income"] is not None:
        names = ", ".join(month["label"] for month in summary["months"])
        origin["monthly_income"] = (
            f"From your transactions: average of the {count} most recent complete month{'s' if count != 1 else ''} "
            f"with income ({names}). Edit it if it is not right."
        )
        if count < 3:
            origin["monthly_income"] += f" Only {count} month{'s' if count != 1 else ''} with income found."
    if summary["dti_percent"] is not None:
        categories = ", ".join(summary["selected_names"])
        origin["dti_ratio"] = (
            f"From your transactions: debt payments of {summary['debt_monthly']:,.2f} per month "
            f"({categories}), averaged over the same months, divided by the monthly income."
        )
        if summary["dti_capped"]:
            origin["dti_ratio"] += " The result is above 100%, so 100 is shown."
    return origin


def _render_finance_form():
    """The credit form prefilled with the monthly income and the debt-to-income ratio of the user.

    Only the ids of the debt categories travel in the URL (``debt`` and ``apply``); the income and
    the DTI are calculated here, on the server, from the user's own transactions.
    """
    chosen = request.args.getlist("debt", type=int) if request.args.get("apply") else None
    summary = finance_summary_for_credit(get_current_user().id, chosen)
    form = {}
    if summary["monthly_income"] is not None:
        form["monthly_income"] = f"{summary['monthly_income']:.2f}"
    if summary["dti_percent"] is not None:
        form["dti_ratio"] = f"{summary['dti_percent']:.1f}"
    return render_template(
        "credit/index.html",
        form=_with_client(form),
        finance=summary,
        origin=_finance_origin(summary),
        field_order=FIELD_ORDER,
        numeric_fields=NUMERIC_FIELDS,
        choice_fields=CHOICE_FIELDS,
    )


@bp.route("/", methods=["GET", "POST"])
@roles_required("applicant")
def index():
    """GET: show the customer form. POST: validate, predict, save and show the result.

    ``GET /credit/?source=finance`` opens the form prefilled from the user's transactions.
    """
    if request.method == "GET":
        if request.args.get("source") == "finance":
            return _render_finance_form()
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
        result = scored_prediction(values, get_current_user().id)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return _render_form(request.form, 503)

    saved = save_credit_application({
        **to_record(values),
        **client,
        "risk_label": result["label"],
        "risk_percent": result["risk_percent"],
        # "<code>@<version>", for example lr@2026-11-13.1; None for the placeholder model.
        "model_version": result.get("model_version"),
        "user_id": get_current_user().id,
    })
    # Post/Redirect/Get: reloading the result page never submits the form again.
    flash("Your request was sent. An analyst will review it.", "success")
    return redirect(url_for("credit.result", application_id=saved["id"]))


@bp.route("/requests/<int:application_id>/edit", methods=["GET", "POST"])
@roles_required("applicant")
def edit(application_id):
    """Edit a request in Pending or Documents requested. It is scored again and goes back to Pending."""
    user = get_current_user()
    application = get_credit_application(user.id, application_id)
    if application is None:
        abort(404)
    if not rules.can_applicant_edit(application["status"]):
        flash("Only requests in Pending or Documents requested can be edited.", "danger")
        return redirect(url_for("credit.result", application_id=application_id))
    if request.method == "GET":
        form = {name: str(application[name]) for name in FIELD_ORDER}
        form["client_full_name"] = application["client_full_name"]
        form["client_document"] = application["client_document"]
        return _render_form(form, edit_id=application_id)

    client, client_errors = validate_client(request.form)
    values, errors = validate_form(request.form)
    errors = client_errors + errors
    if errors:
        for message in errors:
            flash(message, "danger")
        return _render_form(request.form, 400, edit_id=application_id)
    try:
        result = scored_prediction(values, user.id)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return _render_form(request.form, 503, edit_id=application_id)
    update_credit_application(user.id, application_id, {
        **to_record(values),
        **client,
        "risk_label": result["label"],
        "risk_percent": result["risk_percent"],
        "model_version": result.get("model_version"),
    })
    flash("Your request was updated and sent again to an analyst.", "success")
    return redirect(url_for("credit.result", application_id=application_id))


@bp.route("/requests/<int:application_id>/withdraw", methods=["POST"])
@roles_required("applicant")
def withdraw(application_id):
    """The applicant withdraws a request in Pending or Documents requested."""
    try:
        found = withdraw_credit_application(get_current_user().id, application_id)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("credit.result", application_id=application_id))
    if not found:
        abort(404)
    flash("Request withdrawn.", "success")
    return redirect(url_for("credit.history"))


@bp.route("/history")
@roles_required("applicant")
def history():
    """List the current user's past evaluations, newest first, one page (?page=N) at a time."""
    page = paginate_credit_applications(
        get_current_user().id,
        request.args.get("page", 1, type=int),
        current_app.config["PAGE_SIZE"],
    )
    return render_template("credit/history.html", applications=page["items"], pagination=page, rules=rules)


@bp.route("/history/<int:application_id>/delete", methods=["GET", "POST"])
@roles_required("applicant")
def delete(application_id):
    """GET: ask for confirmation (nothing is deleted). POST: delete.

    Evaluations are never edited. Someone else's id answers 404, like a missing one.
    """
    user_id = get_current_user().id
    application = get_credit_application(user_id, application_id)
    if application is None:
        abort(404)
    if not rules.can_applicant_delete(application["status"]):
        flash("A request that was decided cannot be deleted.", "danger")
        return redirect(url_for("credit.history"))
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
@roles_required("applicant")
def result_without_id():
    """Old address without an id: the results now live in the history."""
    return redirect(url_for("credit.history"))


@bp.route("/result/<int:application_id>")
@roles_required("applicant")
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
    return render_template("credit/result.html", result=result, application=application, rules=rules)


@bp.app_template_filter("model_label")
def model_label(model_version):
    """Full model name and artifact version of a stored model_version, never the short code."""
    name, version = parse_model_version_tag(model_version)
    if name is None:
        return "Placeholder model (synthetic data)"
    return f"{DISPLAY_NAMES[name]} (version {version})"


def can_test_models():
    """True for an analyst or administrator, who see the prediction forms of the models page."""
    user = get_current_user()
    return user is not None and user.role in ("analyst", "admin")


def _render_models(active="comparison", form=None, result=None, status=200):
    """The tabbed model page: one tab per model plus the comparison."""
    registry = get_registry()
    catalog = registry.catalog()
    return render_template(
        "credit/models.html",
        catalog=catalog,
        selection=registry.selection_summary(catalog),
        margin=CHAMPION_AUC_MARGIN,
        active=active,
        can_test=can_test_models(),
        form=form or {},
        result=result,
        field_order=FIELD_ORDER,
        numeric_fields=NUMERIC_FIELDS,
        choice_fields=CHOICE_FIELDS,
    ), status


@bp.route("/models/")
def models():
    """Tabs: Logistic Regression, Random Forest, XGBoost and Comparison. Public and read only; staff can also try a model."""
    return _render_models()


@bp.route("/models/<name>/")
def model_detail(name):
    """Old address of one model: it now lives in a tab of /credit/models/. Unknown names answer 404."""
    if name not in MODEL_NAMES:
        abort(404)
    if name not in get_registry().catalog()["metrics"]:
        abort(404)
    return redirect(url_for("credit.models") + f"#{name}")


@bp.route("/models/<name>/predict", methods=["POST"])
@roles_required("analyst", "admin")
def model_predict(name):
    """Predict one application with the chosen model. Nothing is saved: it is a comparison tool."""
    if name not in MODEL_NAMES:
        abort(404)
    values, errors = validate_form(request.form)
    if errors:
        for message in errors:
            flash(message, "danger")
        return _render_models(name, request.form, status=400)
    try:
        result = scored_prediction(values, get_current_user().id, model=name)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return _render_models(name, request.form, status=503)
    return _render_models(name, request.form, {**result, "model": name})
