"""Contract for app/models.py (teammate A).

The database part is done when every test here passes. Then remove the
``pytestmark`` xfail line below so a regression fails the build.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import inspect

from app.extensions import db
from app.models import Budget, Category, Transaction, User

# TODO(teammate A): delete this marker once the models are implemented.
pytestmark = pytest.mark.xfail(reason="Pending teammate A: implement app/models.py", strict=False)

MODELS = {
    User: "users",
    Category: "categories",
    Transaction: "transactions",
    Budget: "budgets",
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
]

FOREIGN_KEYS = [
    (Category, "user_id", "users.id"),
    (Transaction, "user_id", "users.id"),
    (Transaction, "category_id", "categories.id"),
    (Budget, "user_id", "users.id"),
    (Budget, "category_id", "categories.id"),
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


@pytest.mark.parametrize("column", ["username", "email"])
def test_user_column_is_unique(column):
    assert _columns(User)[column].unique is True


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
