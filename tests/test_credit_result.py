"""Tests for the credit result page, loaded from the database by id and owner."""
import re

import pytest

from app.auth.services import register_user
from app.models import CreditApplication

PASSWORD = "a-long-password"
CREDIT_FORM = {
    "client_full_name": "Maria Lopez", "client_document": "100200300",
    "age": "35", "monthly_income": "4000", "employment_status": "employed", "years_employment": "8",
    "credit_score": "760", "existing_debt": "2000", "dti_ratio": "15", "loan_amount": "10000",
    "loan_term": "36", "previous_loans": "2", "payment_history": "good",
}


@pytest.fixture(autouse=True)
def auth_on(app):
    app.config["AUTH_ENABLED"] = True


def logged_in(app, name):
    register_user(name, f"{name}@example.com", PASSWORD)
    client = app.test_client()
    client.post("/auth/login", data={"email": f"{name}@example.com", "password": PASSWORD})
    return client


@pytest.fixture
def ana(app):
    return logged_in(app, "ana")


@pytest.fixture
def luis(app):
    return logged_in(app, "luis")


def evaluate(client):
    """Submit the form and return the result address it redirects to."""
    response = client.post("/credit/", data=CREDIT_FORM)
    assert response.status_code == 302
    return response.headers["Location"]


def test_submitting_redirects_to_the_saved_result(ana):
    location = evaluate(ana)
    (saved,) = CreditApplication.query.all()
    assert location == f"/credit/result/{saved.id}"

    html = ana.get(location).get_data(as_text=True)
    assert saved.risk_label in html
    assert f"{saved.risk_percent}%" in html
    assert "Maria Lopez" in html and "100200300" in html
    assert "Recommendation:" in html


def test_reloading_the_result_creates_no_new_evaluation(ana):
    location = evaluate(ana)
    for _ in range(3):
        assert ana.get(location).status_code == 200
    assert CreditApplication.query.count() == 1


def test_the_result_is_not_kept_in_the_session(ana):
    evaluate(ana)
    with ana.session_transaction() as client_session:
        assert "credit_result" not in client_session
        assert set(client_session) <= {"user_id", "_permanent", "_flashes", "csrf_token"}


def test_someone_elses_result_answers_404(ana, luis):
    location = evaluate(ana)
    response = luis.get(location)
    assert response.status_code == 404
    assert "Maria Lopez" not in response.get_data(as_text=True)


def test_a_deleted_or_missing_result_answers_404(ana):
    location = evaluate(ana)
    application_id = int(location.rsplit("/", 1)[1])
    ana.post(f"/credit/history/{application_id}/delete")
    assert ana.get(location).status_code == 404
    assert ana.get("/credit/result/9999").status_code == 404


def test_the_result_requires_login(app, ana):
    location = evaluate(ana)
    response = app.test_client().get(location)
    assert response.headers["Location"].startswith("/auth/login")


def test_the_history_links_to_each_result(ana):
    first = evaluate(ana)
    second = evaluate(ana)
    html = ana.get("/credit/history").get_data(as_text=True)
    assert f'href="{first}"' in html and f'href="{second}"' in html


def test_the_old_address_without_id_goes_to_the_history(ana):
    response = ana.get("/credit/result")
    assert response.status_code == 302
    assert response.headers["Location"] == "/credit/history"


def test_the_recommendation_matches_the_stored_label(ana):
    from app.credit.services import RECOMMENDATIONS

    location = evaluate(ana)
    label = CreditApplication.query.one().risk_label
    html = ana.get(location).get_data(as_text=True)
    assert RECOMMENDATIONS[label] in html
    assert re.search(r"badge text-bg-(success|warning|danger)", html)
