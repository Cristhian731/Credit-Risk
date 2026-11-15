"""Administrator pages. Only an administrator changes roles; nobody can give themselves privileges."""
import csv
import io

from flask import Response, abort, flash, redirect, render_template, request, url_for

from ..auth.services import DEMO_EMAIL, roles_required
from ..extensions import db
from ..models import ROLES, Budget, Category, Transaction, User
from ..services import indicators
from . import bp

PLACEHOLDER_ENDPOINTS = set()


@bp.route("/")
@roles_required("admin")
def users():
    """List the users with their role and a form to change it."""
    rows = db.session.execute(db.select(User).order_by(User.id)).scalars().all()
    return render_template("admin/users.html", users=rows, roles=ROLES)


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@roles_required("admin")
def change_role(user_id):
    """Change the role of a user. The last administrator cannot lose the role."""
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    role = request.form.get("role", "")
    if role not in ROLES:
        flash("Choose a valid role.", "danger")
        return redirect(url_for("admin.users"))
    if user.email == DEMO_EMAIL and role != "applicant":
        flash("The public demo account is always an applicant.", "danger")
        return redirect(url_for("admin.users"))
    if user.role == "admin" and role != "admin":
        admins = db.session.execute(
            db.select(db.func.count()).select_from(User).filter_by(role="admin")
        ).scalar_one()
        if admins <= 1:
            flash("The last administrator cannot be demoted.", "danger")
            return redirect(url_for("admin.users"))
    user.role = role
    db.session.commit()
    flash(f"{user.username} is now {role}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/categories")
@roles_required("admin")
def categories():
    """Every category of every user, with its use. Unused ones can be renamed or deleted."""
    return render_template("admin/categories.html", rows=indicators.category_usage())


@bp.route("/categories/<int:category_id>/rename", methods=["POST"])
@roles_required("admin")
def rename_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        abort(404)
    name = " ".join(request.form.get("name", "").split())
    if not 1 <= len(name) <= 50:
        flash("The name needs 1 to 50 characters.", "danger")
        return redirect(url_for("admin.categories"))
    clash = db.session.execute(
        db.select(Category.id).where(
            Category.user_id == category.user_id,
            Category.type == category.type,
            db.func.lower(Category.name) == name.lower(),
            Category.id != category.id,
        )
    ).first()
    if clash:
        flash("That user already has a category with this name and type.", "danger")
        return redirect(url_for("admin.categories"))
    category.name = name
    db.session.commit()
    flash("Category renamed.", "success")
    return redirect(url_for("admin.categories"))


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        abort(404)
    used = db.session.execute(
        db.select(db.func.count()).select_from(Transaction).where(Transaction.category_id == category_id)
    ).scalar_one() + db.session.execute(
        db.select(db.func.count()).select_from(Budget).where(Budget.category_id == category_id)
    ).scalar_one()
    if used:
        flash("A category in use cannot be deleted.", "danger")
        return redirect(url_for("admin.categories"))
    db.session.delete(category)
    db.session.commit()
    flash("Category deleted.", "success")
    return redirect(url_for("admin.categories"))


@bp.route("/monitoring")
@roles_required("admin")
def monitoring():
    """Inference log, errors, response times and the comparison of predictions with real outcomes."""
    metrics = indicators.inference_metrics()
    comparison = indicators.prediction_vs_outcome()
    return render_template(
        "admin/monitoring.html",
        metrics=metrics,
        comparison=comparison,
        recent=indicators.recent_inferences(25),
        errors=indicators.recent_inferences(10, only_errors=True),
        checks=operational_review(metrics, comparison),
    )


# Thresholds of the initial operational review (documented in the report and in the monitoring page).
MAX_ERROR_RATE = 5.0
MAX_P95_MS = 2000.0
MIN_OUTCOMES_FOR_RETRAINING_DECISION = 30


def operational_review(metrics, comparison):
    """The checks of the initial operational review, with the live values. Each is (name, value, ok)."""
    calls = metrics["calls"]
    return [
        ("Inference calls recorded", calls, calls > 0),
        ("Error rate below %.0f%%" % MAX_ERROR_RATE, "-" if metrics["error_rate"] is None else f"{metrics['error_rate']}%",
         metrics["error_rate"] is not None and metrics["error_rate"] < MAX_ERROR_RATE),
        ("95th percentile of the response time below %d ms" % MAX_P95_MS,
         "-" if metrics["p95_ms"] is None else f"{metrics['p95_ms']} ms",
         metrics["p95_ms"] is not None and metrics["p95_ms"] < MAX_P95_MS),
        ("Real outcomes recorded (at least %d to judge the model)" % MIN_OUTCOMES_FOR_RETRAINING_DECISION,
         comparison["outcomes"], comparison["outcomes"] >= MIN_OUTCOMES_FOR_RETRAINING_DECISION),
    ]


@bp.route("/reports")
@roles_required("admin")
def reports():
    """Summary report of the flow, with the CSV export of the decisions."""
    return render_template(
        "admin/reports.html",
        data=indicators.request_indicators(),
        comparison=indicators.prediction_vs_outcome(),
        metrics=indicators.inference_metrics(),
    )


@bp.route("/reports/decisions.csv")
@roles_required("admin")
def decisions_csv():
    """Every decision as CSV. It holds no name and no document number."""
    rows = indicators.decisions_export()
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["request_id", "requested_at", "decided_at", "risk_label", "risk_percent", "model_version",
                    "decision", "followed_model", "mandatory_review", "outcome"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=decisions.csv"},
    )
