"""Contract for app/models.py (teammate A).

The database part is done when every test here passes. Then remove the
``pytestmark`` xfail line below so a regression fails the build.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import inspect

from app.extensions import db
from app.models import Budget, Category, Client, CreditApplication, Transaction, User
from ml.features import FEATURE_ORDER

# TODO(teammate A): delete this marker once the models are implemented.
pytestmark = pytest.mark.xfail(reason="Pending teammate A: implement app/models.py", strict=False)

MODELS = {
    User: "users",
    Category: "categories",
    Transaction: "transactions",
    Budget: "budgets",
    Client: "clients",
    CreditApplication: "credit_applications",
}

REQUIRED_COLUMNS = [
    (User, "username"),
    (User, "email"),
    (User, "password_hash"),
    (User, "created_at"),
    (Category, "name"),
    (Category, "type"),
    (Category, "user_id"),
    (Transaction, "type"),
    (Transaction, "amount"),
    (Transaction, "date"),
    (Transaction, "category_id"),
    (Transaction, "user_id"),
    (Budget, "amount"),
    (Budget, "month"),
    (Budget, "category_id"),
    (Budget, "user_id"),
    (Client, "full_name"),
    (Client, "document_number"),
    (Client, "user_id"),
    (Client, "created_at"),
    *[(CreditApplication, name) for name in FEATURE_ORDER],
    (CreditApplication, "risk_label"),
    (CreditApplication, "risk_percent"),
    (CreditApplication, "client_id"),
    (CreditApplication, "user_id"),
    (CreditApplication, "created_at"),
]

FOREIGN_KEYS = [
    (Category, "user_id", "users.id"),
    (Transaction, "user_id", "users.id"),
    (Transaction, "category_id", "categories.id"),
    (Budget, "user_id", "users.id"),
    (Budget, "category_id", "categories.id"),
    (Client, "user_id", "users.id"),
    (CreditApplication, "client_id", "clients.id"),
    (CreditApplication, "user_id", "users.id"),
]

RELATIONSHIPS = [
    (User, "categories", Category, True),
    (User, "transactions", Transaction, True),
    (User, "budgets", Budget, True),
    (Category, "user", User, False),
    (Category, "transactions", Transaction, True),
    (Category, "budgets", Budget, True),
    (Transaction, "user", User, False),
    (Transaction, "category", Category, False),
    (Budget, "user", User, False),
    (Budget, "category", Category, False),
    (User, "clients", Client, True),
    (User, "credit_applications", CreditApplication, True),
    (Client, "user", User, False),
    (Client, "credit_applications", CreditApplication, True),
    (CreditApplication, "client", Client, False),
    (CreditApplication, "user", User, False),
]


def _columns(model):
    return model.__table__.columns


def _make_user_and_category():
    user = User(username="ana", email="ana@example.com", password_hash="hashed")
    category = Category(name="Food", type="expense", user=user)
    db.session.add_all([user, category])
    db.session.commit()
    return user, category


@pytest.mark.parametrize("model, table_name", MODELS.items())
def test_model_is_sqlalchemy_model_with_expected_table(model, table_name):
    assert issubclass(model, db.Model)
    assert model.__tablename__ == table_name


@pytest.mark.parametrize("model", MODELS)
def test_model_has_integer_primary_key(model):
    primary_key = [column.name for column in model.__table__.primary_key]
    assert primary_key == ["id"]


@pytest.mark.parametrize("model, column", REQUIRED_COLUMNS)
def test_required_column(model, column):
    assert column in _columns(model), f"{model.__name__}.{column} is missing"
    assert _columns(model)[column].nullable is False


def test_transaction_description_is_optional():
    assert _columns(Transaction)["description"].nullable is True


@pytest.mark.parametrize("model, column", [(User, "username"), (User, "email"), (Client, "document_number")])
def test_column_is_unique(model, column):
    assert _columns(model)[column].unique is True


def test_credit_application_uses_credit_form_field_names():
    from app.credit.forms import CHOICE_FIELDS, NUMERIC_FIELDS

    form_fields = set(NUMERIC_FIELDS) | set(CHOICE_FIELDS)
    assert form_fields <= set(_columns(CreditApplication).keys())


@pytest.mark.parametrize("model, column, target", FOREIGN_KEYS)
def test_foreign_key(model, column, target):
    targets = {fk.target_fullname for fk in _columns(model)[column].foreign_keys}
    assert target in targets


@pytest.mark.parametrize("model, name, target, is_list", RELATIONSHIPS)
def test_relationship(model, name, target, is_list):
    relationships = inspect(model).relationships
    assert name in relationships, f"{model.__name__}.{name} is missing"
    assert relationships[name].mapper.class_ is target
    assert relationships[name].uselist is is_list


def test_objects_are_linked_after_saving(app):
    user, category = _make_user_and_category()
    transaction = Transaction(
        type="expense",
        amount=Decimal("120500.00"),
        date=date(2026, 11, 4),
        description="Groceries",
        user=user,
        category=category,
    )
    budget = Budget(amount=Decimal("600000.00"), month=date(2026, 11, 1), user=user, category=category)
    db.session.add_all([transaction, budget])
    db.session.commit()

    assert user.transactions == [transaction]
    assert user.budgets == [budget]
    assert category.transactions == [transaction]
    assert transaction.amount == Decimal("120500.00")
    assert user.created_at is not None


@pytest.mark.parametrize("value", ["income", "expense"])
def test_transaction_accepts_valid_type(app, value):
    user, category = _make_user_and_category()
    db.session.add(
        Transaction(type=value, amount=Decimal("1.00"), date=date(2026, 11, 1), user=user, category=category)
    )
    db.session.commit()


def test_transaction_rejects_unknown_type(app):
    user, category = _make_user_and_category()
    with pytest.raises(Exception):
        db.session.add(
            Transaction(type="transfer", amount=Decimal("1.00"), date=date(2026, 11, 1), user=user, category=category)
        )
        db.session.commit()
    db.session.rollback()


def test_transaction_requires_amount(app):
    user, category = _make_user_and_category()
    with pytest.raises(Exception):
        db.session.add(Transaction(type="income", date=date(2026, 11, 1), user=user, category=category))
        db.session.commit()
    db.session.rollback()


def test_credit_application_is_linked_to_client_and_user(app):
    user, _category = _make_user_and_category()
    client = Client(full_name="Laura Gomez", document_number="1012345678", user=user)
    application = CreditApplication(
        age=35,
        monthly_income=Decimal("4000.00"),
        employment_status="employed",
        years_employment=8,
        credit_score=760,
        existing_debt=Decimal("2000.00"),
        dti_ratio=15,
        loan_amount=Decimal("10000.00"),
        loan_term=36,
        previous_loans=2,
        payment_history="good",
        risk_label="Approved",
        risk_percent=3.3,
        client=client,
        user=user,
    )
    db.session.add_all([client, application])
    db.session.commit()

    assert client.credit_applications == [application]
    assert user.clients == [client]
    assert user.credit_applications == [application]
    assert application.created_at is not None
