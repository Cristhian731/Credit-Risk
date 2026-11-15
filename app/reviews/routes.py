"""Analyst pages: the review queue, the decision of a request, the outcome and the decisions history.

Only an analyst or an administrator reaches them (BR2). The indicators page is in block D4.
"""
from flask import abort, current_app, flash, redirect, render_template, request, url_for

from ..auth.services import get_current_user, roles_required
from ..models import DECISIONS, OUTCOMES
from ..services import rules
from ..services.repository import (
    get_application_any,
    paginate_decided_applications,
    record_outcome,
    review_queue,
    save_review,
)
from . import bp

PLACEHOLDER_ENDPOINTS = {"reviews.indicators"}

DECISION_CHOICES = (
    ("Approved", "Approve"),
    ("Rejected", "Reject"),
    ("Documents requested", "Request documents"),
)


def _render_detail(application, status=200):
    return render_template(
        "reviews/detail.html",
        a=application,
        decisions=DECISION_CHOICES,
        outcomes=OUTCOMES,
        rules=rules,
        form=request.form if request.method == "POST" else {},
    ), status


@bp.route("/")
@roles_required("analyst", "admin")
def queue():
    """Pending requests, mandatory review first and then the oldest first."""
    return render_template("reviews/queue.html", items=review_queue())


@bp.route("/history")
@roles_required("analyst", "admin")
def history():
    """Requests that were decided, most recent decision first."""
    page = paginate_decided_applications(request.args.get("page", 1, type=int), current_app.config["PAGE_SIZE"])
    return render_template("reviews/history.html", applications=page["items"], pagination=page)


@bp.route("/<int:application_id>")
@roles_required("analyst", "admin")
def detail(application_id):
    """One request with its data, the model result, the decisions so far and the forms to decide."""
    application = get_application_any(application_id)
    if application is None:
        abort(404)
    return _render_detail(application)


@bp.route("/<int:application_id>/decide", methods=["POST"])
@roles_required("analyst", "admin")
def decide(application_id):
    """Approve, reject or request documents, always with a justification (BR4, BR5, BR7)."""
    application = get_application_any(application_id)
    if application is None:
        abort(404)
    if application["status"] != "Pending":
        flash("Only Pending requests can be decided.", "danger")
        return redirect(url_for("reviews.detail", application_id=application_id))
    decision = request.form.get("decision", "")
    justification, errors = rules.validate_decision(
        decision, request.form.get("justification"), application["age"], bool(request.form.get("human_review"))
    )
    if errors:
        for message in errors:
            flash(message, "danger")
        return _render_detail(application, 400)
    assert decision in DECISIONS
    save_review(get_current_user().id, application_id, decision, justification)
    flash(f"Decision saved: {decision}.", "success")
    return redirect(url_for("reviews.queue"))


@bp.route("/<int:application_id>/outcome", methods=["POST"])
@roles_required("analyst", "admin")
def outcome(application_id):
    """Record once the real outcome (Repaid or Defaulted) of an Approved request (BR6)."""
    value = request.form.get("outcome", "")
    if value not in OUTCOMES:
        flash("Choose Repaid or Defaulted.", "danger")
        return redirect(url_for("reviews.detail", application_id=application_id))
    try:
        record_outcome(application_id, value)
    except LookupError:
        abort(404)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("reviews.detail", application_id=application_id))
    flash(f"Outcome recorded: {value}.", "success")
    return redirect(url_for("reviews.detail", application_id=application_id))


@bp.route("/indicators")
@roles_required("analyst", "admin")
def indicators():
    """Indicators (block D4)."""
    return render_template("placeholder.html", title="Indicators", block="D4")
