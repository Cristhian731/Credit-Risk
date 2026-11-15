"""Indicators and monitoring of the credit request flow.

Everything is calculated when it is read (BR8): nothing here is stored. The functions return plain
dicts and lists so the templates do not depend on the ORM.
"""
from statistics import median

from sqlalchemy import func

from ..extensions import db
from ..models import STATUSES, CreditApplication, Category, InferenceLog, Review, Transaction, User

# Minimum number of real outcomes of each class before AUC and recall are shown as a result.
MIN_OUTCOMES_PER_CLASS = 1


def _percent(part, whole):
    return None if not whole else round(100 * part / whole, 1)


def request_indicators():
    """Requests by status, approval rate, risk distribution, model vs. analyst and decision times."""
    status_rows = dict(
        db.session.execute(
            db.select(CreditApplication.status, func.count(CreditApplication.id)).group_by(CreditApplication.status)
        ).all()
    )
    by_status = {status: status_rows.get(status, 0) for status in STATUSES}
    decided = by_status["Approved"] + by_status["Rejected"]

    risk_rows = dict(
        db.session.execute(
            db.select(CreditApplication.risk_label, func.count(CreditApplication.id)).group_by(
                CreditApplication.risk_label
            )
        ).all()
    )
    risk = {label: risk_rows.get(label, 0) for label in ("Approved", "Medium Risk", "High Risk")}

    # The latest review of each request is its current decision.
    last_ids = db.select(func.max(Review.id)).group_by(Review.application_id)
    reviews = db.session.execute(db.select(Review).where(Review.id.in_(last_ids))).scalars().all()
    followed = sum(1 for r in reviews if r.followed_model is True)
    contradicted = sum(1 for r in reviews if r.followed_model is False)
    no_clear = sum(1 for r in reviews if r.followed_model is None)

    # Decision time: from the request to its FIRST review, in hours.
    first = (
        db.select(Review.application_id, func.min(Review.decided_at).label("decided_at"))
        .group_by(Review.application_id)
        .subquery()
    )
    pairs = db.session.execute(
        db.select(CreditApplication.created_at, first.c.decided_at).join(
            first, first.c.application_id == CreditApplication.id
        )
    ).all()
    hours = sorted(max((decided_at - created_at).total_seconds(), 0) / 3600 for created_at, decided_at in pairs)

    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "approval_rate": _percent(by_status["Approved"], decided),
        "risk": risk,
        "reviews": len(reviews),
        "followed": followed,
        "contradicted": contradicted,
        "no_clear": no_clear,
        "coincidence_rate": _percent(followed, followed + contradicted),
        "decision_hours_mean": round(sum(hours) / len(hours), 2) if hours else None,
        "decision_hours_median": round(median(hours), 2) if hours else None,
        "decision_hours_max": round(hours[-1], 2) if hours else None,
        "decisions_timed": len(hours),
    }


def _auc(scores_positive, scores_negative):
    """ROC AUC as the probability that a defaulter has a higher score than a payer (ties count half)."""
    wins = 0.0
    for p in scores_positive:
        for n in scores_negative:
            wins += 1.0 if p > n else 0.5 if p == n else 0.0
    return wins / (len(scores_positive) * len(scores_negative))


def prediction_vs_outcome():
    """Compare the predictions of the model with the real outcomes (Defaulted is the positive class).

    Returns the AUC (from the risk percentage) and the recall of High Risk once there are outcomes of
    both classes, and the confusion table by risk label in any case.
    """
    rows = db.session.execute(
        db.select(CreditApplication.risk_label, CreditApplication.risk_percent, CreditApplication.outcome).where(
            CreditApplication.outcome.is_not(None)
        )
    ).all()
    defaulted = [r.risk_percent for r in rows if r.outcome == "Defaulted"]
    repaid = [r.risk_percent for r in rows if r.outcome == "Repaid"]
    table = {label: {"Repaid": 0, "Defaulted": 0} for label in ("Approved", "Medium Risk", "High Risk")}
    for r in rows:
        table[r.risk_label][r.outcome] += 1
    enough = len(defaulted) >= MIN_OUTCOMES_PER_CLASS and len(repaid) >= MIN_OUTCOMES_PER_CLASS
    flagged = table["High Risk"]["Defaulted"]
    return {
        "outcomes": len(rows),
        "defaulted": len(defaulted),
        "repaid": len(repaid),
        "table": table,
        "enough": enough,
        "auc": round(_auc(defaulted, repaid), 3) if enough else None,
        "recall_high_risk": _percent(flagged, len(defaulted)) if defaulted else None,
        "awaiting": db.session.execute(
            db.select(func.count(CreditApplication.id)).where(
                CreditApplication.status == "Approved", CreditApplication.outcome.is_(None)
            )
        ).scalar_one(),
    }


def inference_metrics():
    """Number of calls, errors and response times (mean, median, p95, max) of the inference log."""
    rows = db.session.execute(
        db.select(InferenceLog.response_ms, InferenceLog.error).order_by(InferenceLog.id)
    ).all()
    times = sorted(ms for ms, error in rows if error is None)
    errors = sum(1 for _ms, error in rows if error is not None)
    p95 = times[min(len(times) - 1, int(0.95 * len(times)))] if times else None
    return {
        "calls": len(rows),
        "errors": errors,
        "error_rate": _percent(errors, len(rows)),
        "mean_ms": round(sum(times) / len(times), 1) if times else None,
        "median_ms": round(median(times), 1) if times else None,
        "p95_ms": round(p95, 1) if p95 is not None else None,
        "max_ms": round(times[-1], 1) if times else None,
    }


def recent_inferences(limit=25, only_errors=False):
    """The latest rows of the inference log (plain dicts, with the username, never the document)."""
    query = db.select(InferenceLog, User.username).outerjoin(User, User.id == InferenceLog.user_id)
    if only_errors:
        query = query.where(InferenceLog.error.is_not(None))
    rows = db.session.execute(query.order_by(InferenceLog.id.desc()).limit(limit)).all()
    return [
        {
            "created_at": log.created_at,
            "user": username or "-",
            "model": log.model,
            "model_version": log.model_version or "-",
            "result": log.result or "-",
            "risk_percent": log.risk_percent,
            "response_ms": log.response_ms,
            "error": log.error,
        }
        for log, username in rows
    ]


def category_usage():
    """Every category with its owner and how many transactions use it (administrator view)."""
    rows = db.session.execute(
        db.select(Category, User.username, func.count(Transaction.id))
        .join(User, User.id == Category.user_id)
        .outerjoin(Transaction, Transaction.category_id == Category.id)
        .group_by(Category.id, User.username)
        .order_by(User.username, Category.type, Category.name)
    ).all()
    return [
        {"id": c.id, "name": c.name, "type": c.type, "user": username, "transactions": count}
        for c, username, count in rows
    ]


def decisions_export():
    """One row per decision for the CSV report (no document number)."""
    rows = db.session.execute(
        db.select(Review, CreditApplication)
        .join(CreditApplication, CreditApplication.id == Review.application_id)
        .order_by(Review.id)
    ).all()
    return [
        {
            "request_id": app_.id,
            "requested_at": app_.created_at.strftime("%Y-%m-%d %H:%M"),
            "decided_at": review.decided_at.strftime("%Y-%m-%d %H:%M"),
            "risk_label": app_.risk_label,
            "risk_percent": app_.risk_percent,
            "model_version": app_.model_version or "",
            "decision": review.decision,
            "followed_model": "" if review.followed_model is None else str(review.followed_model).lower(),
            "mandatory_review": str(review.mandatory).lower(),
            "outcome": app_.outcome or "",
        }
        for review, app_ in rows
    ]
