"""Tests of the credit request flow: statuses, reviews, outcome, inference log and the business rules."""
import pytest

from app.models import CreditApplication, InferenceLog, Review
from app.services import rules
from app.services.repository import review_queue

FORM = {
    "client_full_name": "Maria Lopez", "client_document": "100200300",
    "age": "35", "monthly_income": "4000", "employment_status": "employed", "years_employment": "8",
    "credit_score": "760", "existing_debt": "2000", "dti_ratio": "15", "loan_amount": "10000",
    "loan_term": "36", "previous_loans": "2", "payment_history": "good",
}
RISKY = {**FORM, "credit_score": "350", "payment_history": "poor", "dti_ratio": "95", "years_employment": "0",
         "employment_status": "unemployed", "monthly_income": "300", "existing_debt": "50000"}


def submit(client, **changes):
    response = client.post("/credit/", data={**FORM, **changes})
    assert response.status_code == 302
    return int(response.headers["Location"].rsplit("/", 1)[1])


def decide(client, application_id, decision, text="Reviewed the documents and the history.", **extra):
    return client.post(
        f"/reviews/{application_id}/decide", data={"decision": decision, "justification": text, **extra}
    )


def status_of(application_id):
    return CreditApplication.query.get(application_id).status


# ---------------------------------------------------------------- pure rules

@pytest.mark.parametrize("label,age,expected", [
    ("High Risk", 40, True), ("Approved", 20, True), ("Approved", 18, True), ("Approved", 24, True),
    ("Medium Risk", 25, False), ("Approved", 17, False), ("Approved", 60, False),
])
def test_mandatory_review_rule(label, age, expected):
    assert rules.is_mandatory_review(label, age) is expected


@pytest.mark.parametrize("label,decision,expected", [
    ("Approved", "Approved", True), ("Approved", "Rejected", False),
    ("High Risk", "Rejected", True), ("High Risk", "Approved", False),
    ("Medium Risk", "Approved", None), ("Medium Risk", "Rejected", None),
    ("Approved", "Documents requested", None), ("High Risk", "Documents requested", None),
])
def test_followed_model_rule_br7(label, decision, expected):
    assert rules.followed_model(label, decision) is expected


def test_decision_needs_a_justification_and_young_rejection_a_human_review():
    assert rules.validate_decision("Approved", "short", 40, False)[1]
    assert rules.validate_decision("Approved", "   ", 40, False)[1]
    assert rules.validate_decision("Approved", "A proper justification", 40, False)[1] == []
    assert rules.validate_decision("Rejected", "A proper justification", 20, False)[1]
    text, errors = rules.validate_decision("Rejected", "A proper justification", 20, True)
    assert errors == [] and text.startswith(rules.HUMAN_REVIEW_NOTE)
    assert rules.validate_decision("Maybe", "A proper justification", 40, False)[1]


# ---------------------------------------------------------------- applicant side

def test_new_request_is_pending_scored_and_logged(app, applicant_client):
    application_id = submit(applicant_client)
    application = CreditApplication.query.get(application_id)
    assert application.status == "Pending" and application.outcome is None
    log = InferenceLog.query.one()
    assert log.result == application.risk_label and log.response_ms >= 0 and log.error is None
    assert log.user_id == application.user_id
    html = applicant_client.get(f"/credit/result/{application_id}").get_data(as_text=True)
    assert "Pending" in html and "analyst will review" in html


def test_inference_log_never_holds_the_document(app, applicant_client):
    submit(applicant_client)
    row = InferenceLog.query.one()
    assert "100200300" not in " ".join(str(getattr(row, c.name)) for c in InferenceLog.__table__.columns)


def test_the_form_prefills_the_client_of_the_applicant(app, applicant_client):
    submit(applicant_client)
    html = applicant_client.get("/credit/").get_data(as_text=True)
    assert 'value="Maria Lopez"' in html and 'value="100200300"' in html


def test_applicant_edits_an_open_request_and_it_goes_back_to_pending(app, applicant_client, analyst_client):
    application_id = submit(applicant_client)
    assert decide(analyst_client, application_id, "Documents requested").status_code == 302
    assert status_of(application_id) == "Documents requested"
    page = applicant_client.get(f"/credit/requests/{application_id}/edit")
    assert page.status_code == 200 and "Maria Lopez" in page.get_data(as_text=True)
    response = applicant_client.post(f"/credit/requests/{application_id}/edit", data={**FORM, "loan_amount": "5000"})
    assert response.status_code == 302
    application = CreditApplication.query.get(application_id)
    assert application.status == "Pending" and float(application.loan_amount) == 5000
    assert len(application.reviews) == 1  # the history of decisions is kept
    assert InferenceLog.query.count() == 2  # it was scored again


def test_applicant_withdraws_and_a_withdrawn_request_leaves_the_queue(app, applicant_client, analyst_client):
    application_id = submit(applicant_client)
    assert applicant_client.post(f"/credit/requests/{application_id}/withdraw").status_code == 302
    assert status_of(application_id) == "Withdrawn"
    assert review_queue() == []
    assert decide(analyst_client, application_id, "Approved").status_code == 302  # refused with a message
    assert status_of(application_id) == "Withdrawn"
    assert applicant_client.get(f"/credit/requests/{application_id}/edit").status_code == 302


def test_a_decided_request_cannot_be_edited_withdrawn_or_deleted(app, applicant_client, analyst_client):
    application_id = submit(applicant_client)
    decide(analyst_client, application_id, "Approved")
    assert applicant_client.get(f"/credit/requests/{application_id}/edit").status_code == 302
    assert applicant_client.post(f"/credit/requests/{application_id}/edit", data=FORM).status_code == 302
    applicant_client.post(f"/credit/requests/{application_id}/withdraw")
    applicant_client.post(f"/credit/history/{application_id}/delete")
    assert status_of(application_id) == "Approved"
    assert CreditApplication.query.get(application_id) is not None


def test_applicant_sees_the_status_and_the_justification(app, applicant_client, analyst_client):
    application_id = submit(applicant_client)
    decide(analyst_client, application_id, "Rejected", "The debt is too high for the requested amount.")
    html = applicant_client.get(f"/credit/result/{application_id}").get_data(as_text=True)
    assert "Rejected" in html and "The debt is too high for the requested amount." in html
    assert "Rejected" in applicant_client.get("/credit/history").get_data(as_text=True)


def test_an_applicant_cannot_touch_another_applicants_request(app, applicant_client):
    from tests.conftest import _logged_in_client
    application_id = submit(applicant_client)
    other = app.test_client()
    from app.auth.services import register_user
    register_user("other", "other@example.com", "another-long-password")
    other.post("/auth/login", data={"email": "other@example.com", "password": "another-long-password"})
    assert other.get(f"/credit/requests/{application_id}/edit").status_code == 404
    assert other.post(f"/credit/requests/{application_id}/withdraw").status_code == 404
    assert other.get(f"/credit/result/{application_id}").status_code == 404


# ---------------------------------------------------------------- analyst side

def test_queue_shows_mandatory_reviews_first_then_the_oldest(app, applicant_client, analyst_client):
    old_standard = submit(applicant_client, client_document="DOC-001", age="45")
    young = submit(applicant_client, client_document="DOC-002", age="20")
    standard_2 = submit(applicant_client, client_document="DOC-003", age="50")
    order = [item["id"] for item in review_queue()]
    assert order.index(young) < order.index(old_standard) < order.index(standard_2)
    html = analyst_client.get("/reviews/").get_data(as_text=True)
    assert "Mandatory" in html


def test_decision_requires_a_justification_and_keeps_the_request_pending(app, applicant_client, analyst_client):
    application_id = submit(applicant_client)
    response = decide(analyst_client, application_id, "Approved", "no")
    assert response.status_code == 400
    assert status_of(application_id) == "Pending" and Review.query.count() == 0


def test_rejecting_a_young_applicant_needs_the_human_review_confirmation(app, applicant_client, analyst_client):
    application_id = submit(applicant_client, age="21")
    assert decide(analyst_client, application_id, "Rejected").status_code == 400
    assert decide(analyst_client, application_id, "Rejected", human_review="on").status_code == 302
    review = Review.query.one()
    assert review.justification.startswith(rules.HUMAN_REVIEW_NOTE) and review.mandatory is True


def test_review_stores_the_analyst_the_mandatory_flag_and_followed_model(app, applicant_client, analyst_client):
    application_id = submit(applicant_client)
    label = CreditApplication.query.get(application_id).risk_label
    decide(analyst_client, application_id, "Approved")
    review = Review.query.one()
    assert review.analyst.email == "analyst@example.com"
    assert review.followed_model is rules.followed_model(label, "Approved")


def test_outcome_only_for_approved_and_only_once(app, applicant_client, analyst_client):
    pending = submit(applicant_client, client_document="DOC-010")
    assert analyst_client.post(f"/reviews/{pending}/outcome", data={"outcome": "Repaid"}).status_code == 302
    assert CreditApplication.query.get(pending).outcome is None

    approved = submit(applicant_client, client_document="DOC-011")
    decide(analyst_client, approved, "Approved")
    analyst_client.post(f"/reviews/{approved}/outcome", data={"outcome": "Repaid"})
    assert CreditApplication.query.get(approved).outcome == "Repaid"
    analyst_client.post(f"/reviews/{approved}/outcome", data={"outcome": "Defaulted"})
    assert CreditApplication.query.get(approved).outcome == "Repaid"
    assert analyst_client.post(f"/reviews/{approved}/outcome", data={"outcome": "Lost"}).status_code == 302


def test_history_lists_decisions_with_followed_model(app, applicant_client, analyst_client):
    application_id = submit(applicant_client)
    decide(analyst_client, application_id, "Documents requested")
    html = analyst_client.get("/reviews/history").get_data(as_text=True)
    assert "Documents requested" in html and "No clear recommendation" in html


def test_admin_can_also_decide(app, applicant_client, admin_client):
    application_id = submit(applicant_client)
    assert decide(admin_client, application_id, "Approved").status_code == 302
    assert status_of(application_id) == "Approved"


def test_the_applicant_cannot_decide_or_record_outcomes(app, applicant_client):
    application_id = submit(applicant_client)
    assert decide(applicant_client, application_id, "Approved").status_code in (302, 403)
    assert applicant_client.post(f"/reviews/{application_id}/outcome", data={"outcome": "Repaid"}).status_code in (302, 403)
    assert status_of(application_id) == "Pending" and Review.query.count() == 0


def test_a_failing_model_is_logged_with_its_error(app, applicant_client, monkeypatch):
    from app.credit import services

    def broken(self, data, model=None):
        raise RuntimeError("The trained models are not available.")

    monkeypatch.setattr(services.ModelRegistry, "predict", broken)
    response = applicant_client.post("/credit/", data=FORM)
    assert response.status_code == 503
    log = InferenceLog.query.one()
    assert log.error == "The trained models are not available." and log.result is None
    assert CreditApplication.query.count() == 0
