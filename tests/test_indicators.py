"""Tests of the indicators, the monitoring pages and the admin reports (block D4)."""
import pytest

from app.models import Category, CreditApplication, Review, Transaction
from app.services import indicators
from tests.test_request_flow import FORM, decide, submit


def make_application(client, **changes):
    return submit(client, **changes)


def set_outcome(application_id, outcome):
    from app.extensions import db

    application = db.session.get(CreditApplication, application_id)
    application.outcome = outcome
    db.session.commit()


def test_indicators_are_empty_without_data(app):
    data = indicators.request_indicators()
    assert data["total"] == 0 and data["approval_rate"] is None and data["coincidence_rate"] is None
    assert data["decision_hours_mean"] is None
    assert indicators.inference_metrics()["calls"] == 0
    assert indicators.prediction_vs_outcome()["enough"] is False


def test_indicators_count_statuses_approval_rate_and_coincidence(app, applicant_client, analyst_client):
    ids = [make_application(applicant_client, client_document=f"DOC-10{i}") for i in range(4)]
    decide(analyst_client, ids[0], "Approved")
    decide(analyst_client, ids[1], "Rejected")
    decide(analyst_client, ids[2], "Documents requested")
    data = indicators.request_indicators()
    assert data["by_status"]["Approved"] == 1 and data["by_status"]["Rejected"] == 1
    assert data["by_status"]["Documents requested"] == 1 and data["by_status"]["Pending"] == 1
    assert data["total"] == 4 and data["approval_rate"] == 50.0
    assert data["no_clear"] >= 1 and data["reviews"] == 3
    assert data["decisions_timed"] == 3 and data["decision_hours_mean"] >= 0
    assert sum(data["risk"].values()) == 4


def test_real_auc_and_recall_when_both_classes_exist(app, applicant_client, analyst_client):
    good = make_application(applicant_client, client_document="DOC-201")
    bad = make_application(
        applicant_client, client_document="DOC-202", credit_score="350", payment_history="poor",
        dti_ratio="95", years_employment="0", employment_status="unemployed", monthly_income="300",
        existing_debt="50000",
    )
    decide(analyst_client, good, "Approved")
    decide(analyst_client, bad, "Approved")
    set_outcome(good, "Repaid")
    set_outcome(bad, "Defaulted")
    result = indicators.prediction_vs_outcome()
    assert result["enough"] and result["outcomes"] == 2
    assert result["auc"] == 1.0  # the riskier request is the one that defaulted
    assert result["recall_high_risk"] in (0.0, 100.0)


def test_auc_with_ties_counts_half():
    assert indicators._auc([50.0], [50.0]) == 0.5
    assert indicators._auc([80.0, 10.0], [50.0]) == 0.5


def test_inference_metrics_and_recent_rows(app, applicant_client):
    make_application(applicant_client)
    metrics = indicators.inference_metrics()
    assert metrics["calls"] == 1 and metrics["errors"] == 0 and metrics["error_rate"] == 0.0
    assert metrics["p95_ms"] is not None
    (row,) = indicators.recent_inferences()
    assert row["user"] == "applicant" and "100200300" not in str(row)


def test_indicators_page_is_for_staff_only(app, applicant_client, analyst_client):
    assert "Requests by status" in analyst_client.get("/reviews/indicators").get_data(as_text=True)
    assert applicant_client.get("/reviews/indicators").status_code in (302, 403)


def test_admin_pages_render_and_are_admin_only(app, applicant_client, analyst_client, admin_client):
    make_application(applicant_client)
    for path in ("/admin/monitoring", "/admin/reports", "/admin/categories", "/admin/reports/decisions.csv"):
        assert admin_client.get(path).status_code == 200
        assert analyst_client.get(path).status_code in (302, 403)
        assert applicant_client.get(path).status_code in (302, 403)
    html = admin_client.get("/admin/monitoring").get_data(as_text=True)
    assert "Initial operational review" in html and "Latest inferences" in html


def test_decisions_csv_has_no_personal_data(app, applicant_client, analyst_client, admin_client):
    application_id = make_application(applicant_client)
    decide(analyst_client, application_id, "Approved")
    response = admin_client.get("/admin/reports/decisions.csv")
    text = response.get_data(as_text=True)
    assert response.mimetype == "text/csv" and "Approved" in text
    assert "Maria" not in text and "100200300" not in text
    assert text.splitlines()[0].startswith("request_id,")


def test_admin_renames_and_deletes_categories_only_when_unused(app, applicant_client, admin_client):
    from app.extensions import db
    from app.models import User

    user = User.query.filter_by(email="applicant@example.com").one()
    used = Category(name="Food", type="expense", user_id=user.id)
    free = Category(name="Spare", type="expense", user_id=user.id)
    db.session.add_all([used, free])
    db.session.flush()
    from datetime import date
    db.session.add(Transaction(type="expense", amount=5, date=date(2026, 1, 1), category_id=used.id, user_id=user.id))
    db.session.commit()

    assert admin_client.post(f"/admin/categories/{used.id}/rename", data={"name": "Groceries"}).status_code == 302
    assert db.session.get(Category, used.id).name == "Groceries"
    admin_client.post(f"/admin/categories/{used.id}/delete")
    assert db.session.get(Category, used.id) is not None
    admin_client.post(f"/admin/categories/{free.id}/delete")
    assert db.session.get(Category, free.id) is None
    admin_client.post(f"/admin/categories/{used.id}/rename", data={"name": ""})
    assert db.session.get(Category, used.id).name == "Groceries"
