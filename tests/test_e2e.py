"""End-to-end journey, as a user would do it, with the production-like settings.

Migrated database file, real authentication and CSRF on (tokens read from the
pages), and an application restart in the middle to prove the data persists:
register -> log in -> dashboard -> transactions (add, edit, delete) ->
credit evaluation -> result -> history -> restart -> log in -> logout.
"""
import re

import pytest
from flask_migrate import upgrade

from app import create_app
from app.extensions import db
from config import TestingConfig

PASSWORD = "a-long-password"
CREDIT_FORM = {
    "client_full_name": "Maria Lopez", "client_document": "100200300",
    "age": "35", "monthly_income": "4000", "employment_status": "employed", "years_employment": "8",
    "credit_score": "760", "existing_debt": "2000", "dti_ratio": "15", "loan_amount": "10000",
    "loan_term": "36", "previous_loans": "2", "payment_history": "good",
}


@pytest.fixture
def start_app(tmp_path, monkeypatch):
    """Start (or restart) the application on the same migrated database file."""
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'e2e.db'}")
    started = []

    def start():
        for previous in started:  # stop the previous "process"
            with previous.app_context():
                db.session.remove()
                db.engine.dispose()
        application = create_app("testing")
        application.config.update(AUTH_ENABLED=True, WTF_CSRF_ENABLED=True)
        if not started:
            with application.app_context():
                upgrade()
        started.append(application)
        return application

    yield start
    for application in started:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()


class Browser:
    """A test client that reads the CSRF token from each page, like a browser form."""

    def __init__(self, application):
        self.client = application.test_client()

    def get(self, path):
        return self.client.get(path, follow_redirects=True)

    def submit(self, page, action, data=None):
        html = self.client.get(page).get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        return self.client.post(action, data={**(data or {}), "csrf_token": token}, follow_redirects=True)


def totals(html):
    return dict(re.findall(r"<h5 class=\"text-muted\">([^<]+)</h5>\s*<p[^>]*>([^<]+)</p>", html))


def test_full_journey_survives_a_restart(start_app):
    browser = Browser(start_app())

    # Register and log in: the user lands on an empty dashboard.
    page = browser.submit("/auth/register", "/auth/register", {"username": "ana", "email": "ana@example.com", "password": PASSWORD})
    assert "Your account has been created" in page.get_data(as_text=True)
    page = browser.submit("/", "/auth/login", {"email": "ana@example.com", "password": PASSWORD})
    assert page.request.path == "/dashboard/"
    assert totals(page.get_data(as_text=True))["Balance"] == "0.00"

    # Transactions: add two, edit one, delete one.
    for kind, amount, category in (("income", "2500000.00", "Salary"), ("expense", "850000.00", "Housing")):
        page = browser.submit("/transactions/new", "/transactions/new",
                              {"type": kind, "amount": amount, "date": "2026-11-01", "category": category, "description": ""})
        assert "Transaction saved." in page.get_data(as_text=True)
    assert totals(browser.get("/dashboard/").get_data(as_text=True))["Balance"] == "1,650,000.00"

    ids = re.findall(r"/transactions/(\d+)/edit", browser.get("/transactions/").get_data(as_text=True))
    housing = next(i for i in ids if "Housing" in browser.get(f"/transactions/{i}/edit").get_data(as_text=True))
    salary = next(i for i in ids if i != housing)
    page = browser.submit(f"/transactions/{housing}/edit", f"/transactions/{housing}/edit",
                          {"type": "expense", "amount": "900000.00", "date": "2026-11-02", "category": "Rent", "description": "Flat"})
    assert "Transaction updated." in page.get_data(as_text=True)
    assert totals(browser.get("/dashboard/").get_data(as_text=True))["Balance"] == "1,600,000.00"

    page = browser.submit(f"/transactions/{salary}/delete", f"/transactions/{salary}/delete")
    assert "Transaction deleted." in page.get_data(as_text=True)
    assert totals(browser.get("/dashboard/").get_data(as_text=True))["Balance"] == "-900,000.00"

    # Credit evaluation: result page by id, then the history.
    page = browser.submit("/credit/", "/credit/", CREDIT_FORM)
    assert re.fullmatch(r"/credit/result/\d+", page.request.path)
    result_path = page.request.path
    assert "Maria Lopez" in page.get_data(as_text=True)
    history = browser.get("/credit/history").get_data(as_text=True)
    assert "Maria Lopez" in history and f'href="{result_path}"' in history

    # Restart the application: a new browser logs in and finds everything.
    browser = Browser(start_app())
    assert browser.client.get("/dashboard/").headers["Location"] == "/auth/login?next=/dashboard/"  # new session
    page = browser.submit("/", "/auth/login", {"email": "ana@example.com", "password": PASSWORD})
    dashboard = totals(page.get_data(as_text=True))
    assert (dashboard["Balance"], dashboard["Credit evaluations"]) == ("-900,000.00", "1")
    transactions = browser.get("/transactions/").get_data(as_text=True)
    assert "Rent" in transactions and "Salary" not in transactions
    assert "Maria Lopez" in browser.get(result_path).get_data(as_text=True)

    # Log out: private pages ask for the login again.
    page = browser.submit("/dashboard/", "/auth/logout")
    assert "You have successfully logged out." in page.get_data(as_text=True)
    assert browser.client.get("/credit/history").headers["Location"].startswith("/auth/login")
