"""Link between the finance module and the credit evaluation: income and DTI calculated on read."""
import re
from datetime import date
from decimal import Decimal

import pytest

from app.auth.services import register_user
from app.models import Category, CreditApplication, Transaction
from app.services import repository
from app.services.repository import finance_summary_for_credit, is_debt_category_name

TODAY = date(2026, 11, 13)  # complete months before it: October, September, August...
PASSWORD = "correct-horse-battery"

CREDIT_FORM = {
    "client_full_name": "Maria Lopez", "client_document": "100200300",
    "age": "35", "years_employment": "8", "employment_status": "employed", "credit_score": "700",
    "existing_debt": "2000", "loan_amount": "10000", "loan_term": "36", "previous_loans": "2",
    "payment_history": "good",
}


def _add(user_id, kind, amount, when, category):
    return repository.save_transaction({
        "type": kind, "amount": Decimal(str(amount)), "date": when, "category": category,
        "description": "", "user_id": user_id,
    })


def _income(user_id, amount, year, month, category="Salary"):
    return _add(user_id, "income", amount, date(year, month, 10), category)


def _expense(user_id, amount, year, month, category):
    return _add(user_id, "expense", amount, date(year, month, 12), category)


@pytest.fixture
def user_id(demo_user):
    return demo_user.id


@pytest.fixture
def other_user_id(app):
    return register_user("ana", "ana@example.com", PASSWORD).id


@pytest.fixture
def three_months(user_id):
    """Income of 3000, 4000 and 5000 in August, September and October 2026."""
    for month, amount in ((8, 3000), (9, 4000), (10, 5000)):
        _income(user_id, amount, 2026, month)


# Monthly income

def test_income_is_the_average_of_the_three_most_recent_complete_months(user_id):
    for year, month, amount in ((2026, 7, 9000), (2026, 8, 3000), (2026, 9, 4000), (2026, 10, 5000), (2026, 11, 99999)):
        _income(user_id, amount, year, month)
    summary = finance_summary_for_credit(user_id, today=TODAY)
    assert summary["monthly_income"] == Decimal("4000.00")
    assert [m["key"] for m in summary["months"]] == ["2026-10", "2026-09", "2026-08"]
    assert summary["months"][0]["label"] == "October 2026"


def test_months_without_income_are_skipped_not_counted_as_zero(user_id):
    for month, amount in ((10, 5000), (8, 3000), (7, 4000), (6, 6000)):
        _income(user_id, amount, 2026, month)
    summary = finance_summary_for_credit(user_id, today=TODAY)
    assert [m["key"] for m in summary["months"]] == ["2026-10", "2026-08", "2026-07"]
    assert summary["monthly_income"] == Decimal("4000.00")


def test_several_incomes_in_one_month_are_added_up(user_id):
    _income(user_id, 1000, 2026, 10)
    _income(user_id, 500, 2026, 10, category="Freelance")
    _income(user_id, 2500, 2026, 9)
    summary = finance_summary_for_credit(user_id, today=TODAY)
    assert summary["monthly_income"] == Decimal("2000.00")  # (1500 + 2500) / 2


def test_with_fewer_than_three_months_it_uses_the_ones_it_has(user_id):
    _income(user_id, 3333, 2026, 10)
    summary = finance_summary_for_credit(user_id, today=TODAY)
    assert summary["monthly_income"] == Decimal("3333.00")
    assert len(summary["months"]) == 1


def test_the_current_month_is_never_used(user_id):
    _income(user_id, 8000, 2026, 11)
    summary = finance_summary_for_credit(user_id, today=TODAY)
    assert summary["monthly_income"] is None and summary["months"] == []


def test_it_looks_back_at_most_twelve_months(user_id):
    _income(user_id, 2000, 2025, 10)  # 13 months back: outside the window
    assert finance_summary_for_credit(user_id, today=TODAY)["monthly_income"] is None
    _income(user_id, 2400, 2025, 11)  # 12 months back: inside
    summary = finance_summary_for_credit(user_id, today=TODAY)
    assert summary["monthly_income"] == Decimal("2400.00") and summary["months"][0]["key"] == "2025-11"


def test_without_income_nothing_is_calculated(user_id):
    _expense(user_id, 100, 2026, 10, "Food")
    summary = finance_summary_for_credit(user_id, today=TODAY)
    assert summary["monthly_income"] is None
    assert summary["dti_percent"] is None and summary["debt_monthly"] is None


def test_months_wrap_around_the_year(user_id):
    for month, amount in ((11, 1000), (12, 2000)):
        _income(user_id, amount, 2025, month)
    _income(user_id, 3000, 2026, 1)
    summary = finance_summary_for_credit(user_id, today=date(2026, 2, 3))
    assert [m["key"] for m in summary["months"]] == ["2026-01", "2025-12", "2025-11"]
    assert summary["monthly_income"] == Decimal("2000.00")


# Debt payments and DTI

@pytest.fixture
def with_debt(user_id, three_months):
    """A 400 loan payment and 1000 of food in each of the three months, plus a loan payment in July."""
    for month in (8, 9, 10):
        _expense(user_id, 400, 2026, month, "Student loan")
        _expense(user_id, 1000, 2026, month, "Food")
    _expense(user_id, 800, 2026, 7, "Student loan")  # not one of the months used


def _id(summary, name):
    return next(c["id"] for c in summary["expense_categories"] if c["name"] == name)


def test_suggested_debt_categories_are_premarked_and_give_the_dti(user_id, with_debt):
    summary = finance_summary_for_credit(user_id, today=TODAY)
    assert summary["selected_names"] == ["Student loan"]
    assert summary["debt_monthly"] == Decimal("400.00")  # averaged over August, September and October
    assert summary["dti_percent"] == 10.0  # 400 / 4000


def test_the_user_can_choose_other_categories(user_id, with_debt):
    base = finance_summary_for_credit(user_id, today=TODAY)
    both = finance_summary_for_credit(user_id, [_id(base, "Student loan"), _id(base, "Food")], today=TODAY)
    assert both["debt_monthly"] == Decimal("1400.00") and both["dti_percent"] == 35.0
    none = finance_summary_for_credit(user_id, [], today=TODAY)
    assert none["dti_percent"] is None and none["selected_names"] == []
    assert none["monthly_income"] == Decimal("4000.00")


def test_dti_is_capped_at_100(user_id, three_months):
    for month in (8, 9, 10):
        _expense(user_id, 9000, 2026, month, "Credit card")
    summary = finance_summary_for_credit(user_id, today=TODAY)
    assert summary["dti_percent"] == 100.0 and summary["dti_capped"] is True


def test_the_summary_lists_only_expense_categories_with_their_flags(user_id, with_debt):
    _income(user_id, 10, 2026, 10, category="Loan refunds")  # an income category: never listed
    summary = finance_summary_for_credit(user_id, today=TODAY)
    assert [(c["name"], c["suggested"], c["selected"]) for c in summary["expense_categories"]] == [
        ("Food", False, False), ("Student loan", True, True),
    ]


@pytest.mark.parametrize("name, expected", [
    ("Loans", True), ("Credit card", True), ("Préstamo personal", True), ("PRESTAMO", True),
    ("Tarjeta de crédito", True), ("Deuda", True), ("Debt payments", True), ("Mortgage credit", True),
    ("Food", False), ("Rent", False), ("Salary", False), ("", False),
])
def test_debt_suggestion_ignores_case_and_accents(name, expected):
    assert is_debt_category_name(name) is expected


# Isolation and nothing stored

def test_other_users_data_is_never_used(user_id, other_user_id, with_debt):
    _income(other_user_id, 90000, 2026, 10)
    _expense(other_user_id, 50000, 2026, 10, "Student loan")
    foreign = finance_summary_for_credit(other_user_id, today=TODAY)
    mine = finance_summary_for_credit(user_id, today=TODAY)
    assert mine["monthly_income"] == Decimal("4000.00") and mine["dti_percent"] == 10.0
    assert foreign["monthly_income"] == Decimal("90000.00")


def test_category_ids_of_another_user_are_ignored(user_id, other_user_id, with_debt):
    _income(other_user_id, 1000, 2026, 10)
    _expense(other_user_id, 500, 2026, 10, "Student loan")
    foreign_id = _id(finance_summary_for_credit(other_user_id, today=TODAY), "Student loan")
    own_id = _id(finance_summary_for_credit(user_id, today=TODAY), "Student loan")
    assert foreign_id != own_id
    only_foreign = finance_summary_for_credit(user_id, [foreign_id, 999999], today=TODAY)
    assert only_foreign["selected_names"] == [] and only_foreign["dti_percent"] is None
    mixed = finance_summary_for_credit(user_id, [foreign_id, own_id], today=TODAY)
    assert mixed["selected_names"] == ["Student loan"] and mixed["dti_percent"] == 10.0


def test_nothing_is_stored(app, user_id, with_debt):
    from app.extensions import db

    before = [db.session.query(model).count() for model in (Transaction, Category, CreditApplication)]
    finance_summary_for_credit(user_id, today=TODAY)
    finance_summary_for_credit(user_id, [], today=TODAY)
    assert [db.session.query(model).count() for model in (Transaction, Category, CreditApplication)] == before
    assert not {"monthly_income", "dti_ratio"} & {column.name for column in Transaction.__table__.columns}


# Pages

def _months_ago(months):
    today = date.today()
    index = today.year * 12 + today.month - 1 - months
    return index // 12, index % 12 + 1


def _real_data(user_id):
    """Income 4000 and a 400 loan payment plus 1000 of food in each of the 3 months before this one."""
    for months in (1, 2, 3):
        year, month = _months_ago(months)
        _income(user_id, 4000, year, month)
        _expense(user_id, 400, year, month, "Student loan")
        _expense(user_id, 1000, year, month, "Food")


@pytest.fixture
def demo_client(client, demo_user):
    return client


def test_dashboard_has_the_button_to_check_the_credit_risk(demo_client):
    html = demo_client.get("/dashboard/").get_data(as_text=True)
    assert "Check my credit risk" in html
    assert 'href="/credit/?source=finance"' in html


def test_credit_form_opens_prefilled_with_income_and_dti_and_their_origin(demo_client, user_id):
    _real_data(user_id)
    html = demo_client.get("/credit/?source=finance").get_data(as_text=True)
    assert re.search(r'name="monthly_income"[^>]*value="4000.00"', html)
    assert re.search(r'name="dti_ratio"[^>]*value="10.0"', html)
    assert 'data-testid="origin-monthly_income"' in html and "From your transactions" in html
    assert 'data-testid="origin-dti_ratio"' in html and "Student loan" in html
    months = [date(*_months_ago(n), 1).strftime("%B %Y") for n in (1, 2, 3)]
    assert all(label in html for label in months)
    assert 'name="age"' in html and re.search(r'name="age"[^>]*value=""', html)  # the rest is left to the user


def test_only_category_ids_travel_in_the_url(demo_client, user_id):
    _real_data(user_id)
    html = demo_client.get("/credit/?source=finance").get_data(as_text=True)
    panel = html.split('data-testid="finance-panel"')[1].split("</form>")[0]
    assert set(re.findall(r'<input[^>]*type="hidden" name="(\w+)"', panel)) == {"source", "apply"}
    assert set(re.findall(r'name="(\w+)"', panel)) == {"source", "apply", "debt"}
    assert 'href="/credit/?source=finance"' in demo_client.get("/dashboard/").get_data(as_text=True)


def test_recalculating_with_other_categories_changes_the_dti(demo_client, user_id):
    _real_data(user_id)
    food = _id(finance_summary_for_credit(user_id), "Food")
    html = demo_client.get(f"/credit/?source=finance&apply=1&debt={food}").get_data(as_text=True)
    assert re.search(r'name="dti_ratio"[^>]*value="25.0"', html)  # 1000 / 4000
    none = demo_client.get("/credit/?source=finance&apply=1").get_data(as_text=True)
    assert re.search(r'name="dti_ratio"[^>]*value=""', none) and 'data-testid="finance-no-debt"' in none


def test_ids_of_other_users_and_junk_are_ignored_by_the_page(demo_client, user_id, other_user_id):
    _real_data(user_id)
    _income(other_user_id, 1000, *_months_ago(1))
    _expense(other_user_id, 500, *_months_ago(1), "Student loan")
    foreign = _id(finance_summary_for_credit(other_user_id), "Student loan")
    html = demo_client.get(f"/credit/?source=finance&apply=1&debt={foreign}&debt=abc").get_data(as_text=True)
    assert re.search(r'name="dti_ratio"[^>]*value=""', html) and 'data-testid="finance-no-debt"' in html
    assert re.search(r'name="monthly_income"[^>]*value="4000.00"', html)


def test_without_income_the_page_explains_and_leaves_the_fields_empty(demo_client, user_id):
    html = demo_client.get("/credit/?source=finance").get_data(as_text=True)
    assert 'data-testid="finance-no-income"' in html
    assert re.search(r'name="monthly_income"[^>]*value=""', html) and re.search(r'name="dti_ratio"[^>]*value=""', html)


def test_with_one_month_of_income_the_page_says_so(demo_client, user_id):
    _income(user_id, 3000, *_months_ago(1))
    html = demo_client.get("/credit/?source=finance").get_data(as_text=True)
    assert "Only 1 month with income found" in html


def test_the_plain_credit_form_is_unchanged(demo_client, user_id):
    _real_data(user_id)
    html = demo_client.get("/credit/").get_data(as_text=True)
    assert 'data-testid="finance-panel"' not in html
    assert re.search(r'name="monthly_income"[^>]*value=""', html)


def test_another_users_transactions_do_not_reach_the_page(demo_client, user_id, other_user_id):
    _income(other_user_id, 90000, *_months_ago(1))
    html = demo_client.get("/credit/?source=finance").get_data(as_text=True)
    assert 'data-testid="finance-no-income"' in html


def test_the_prefilled_form_is_evaluated_with_the_champion(demo_client, user_id):
    import os

    from ml.features import ARTIFACTS_DIR, MANIFEST_FILENAME
    from ml.schemas import load_json, model_version_tag

    _real_data(user_id)
    prefilled = demo_client.get("/credit/?source=finance").get_data(as_text=True)
    income = re.search(r'name="monthly_income"[^>]*value="([\d.]+)"', prefilled).group(1)
    dti = re.search(r'name="dti_ratio"[^>]*value="([\d.]+)"', prefilled).group(1)
    response = demo_client.post("/credit/", data={**CREDIT_FORM, "monthly_income": income, "dti_ratio": dti})
    assert response.status_code == 302
    (saved,) = repository.list_credit_applications(user_id)
    manifest = load_json(os.path.join(ARTIFACTS_DIR, MANIFEST_FILENAME))
    assert saved["model_version"] == model_version_tag(manifest["champion"], manifest["version"])
    assert (saved["monthly_income"], saved["dti_ratio"]) == (Decimal("4000.00"), 10.0)
