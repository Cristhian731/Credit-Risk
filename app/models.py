"""Database models for Credit Risk (Flask-SQLAlchemy).

Built from the model contract and the DataBase branch. Class, table, column
and relationship names are part of the contract: other modules and
``tests/test_models_contract.py`` depend on them, so keep them unchanged.

Tables are created in ``app.create_app()``, never at import time.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import validates
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

# Allowed values for Category.type and Transaction.type.
TRANSACTION_TYPES = ("income", "expense")

# Allowed values for CreditApplication text columns. They match the option
# values of the credit form and the encodings in ml/features.py.
EMPLOYMENT_STATUSES = ("employed", "self_employed", "retired", "unemployed")
PAYMENT_HISTORIES = ("good", "fair", "poor")
RISK_LABELS = ("Approved", "Medium Risk", "High Risk")


def utcnow():
    return datetime.now(timezone.utc)


def _in_check(column, values):
    """SQL CHECK constraint text: ``column IN ('a', 'b')``."""
    options = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({options})"


def _require_choice(field, value, allowed):
    if value not in allowed:
        raise ValueError(f"{field} must be one of {allowed}, got {value!r}.")
    return value


class User(db.Model):
    """A registered person who owns finances, clients and credit applications."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    categories = db.relationship("Category", back_populates="user")
    transactions = db.relationship("Transaction", back_populates="user")
    budgets = db.relationship("Budget", back_populates="user")
    clients = db.relationship("Client", back_populates="user")
    credit_applications = db.relationship("CreditApplication", back_populates="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    """A label that groups transactions, e.g. "Food" or "Salary"."""

    __tablename__ = "categories"
    __table_args__ = (
        db.CheckConstraint(_in_check("type", TRANSACTION_TYPES), name="ck_categories_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    user = db.relationship("User", back_populates="categories")
    transactions = db.relationship("Transaction", back_populates="category")
    budgets = db.relationship("Budget", back_populates="category")

    @validates("type")
    def _validate_type(self, key, value):
        return _require_choice(key, value, TRANSACTION_TYPES)


class Transaction(db.Model):
    """A single income or expense recorded by a user."""

    __tablename__ = "transactions"
    __table_args__ = (
        db.CheckConstraint(_in_check("type", TRANSACTION_TYPES), name="ck_transactions_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    user = db.relationship("User", back_populates="transactions")
    category = db.relationship("Category", back_populates="transactions")

    @validates("type")
    def _validate_type(self, key, value):
        return _require_choice(key, value, TRANSACTION_TYPES)


class Budget(db.Model):
    """A spending limit for one category in one month."""

    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    month = db.Column(db.Date, nullable=False)  # first day of the budgeted month
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    user = db.relationship("User", back_populates="budgets")
    category = db.relationship("Category", back_populates="budgets")


class Client(db.Model):
    """A customer whose loan applications are evaluated."""

    __tablename__ = "clients"
    # The same document may belong to clients of different users, but a user
    # cannot register it twice.
    __table_args__ = (
        db.UniqueConstraint("user_id", "document_number", name="uq_clients_user_id_document_number"),
    )

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    document_number = db.Column(db.String(30), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="clients")
    credit_applications = db.relationship("CreditApplication", back_populates="client")


class CreditApplication(db.Model):
    """One loan evaluation: the customer data at that moment and the prediction.

    Joins the DataBase branch's CreditProfile, LoanApplication and Prediction
    tables into one row, as the contract requires. Feature columns use the
    names of the credit form fields and ``ml.features.FEATURE_ORDER``.
    """

    __tablename__ = "credit_applications"
    __table_args__ = (
        db.CheckConstraint(
            _in_check("employment_status", EMPLOYMENT_STATUSES),
            name="ck_credit_applications_employment_status",
        ),
        db.CheckConstraint(
            _in_check("payment_history", PAYMENT_HISTORIES),
            name="ck_credit_applications_payment_history",
        ),
        db.CheckConstraint(_in_check("risk_label", RISK_LABELS), name="ck_credit_applications_risk_label"),
    )

    id = db.Column(db.Integer, primary_key=True)

    # Customer data used by the model.
    age = db.Column(db.Integer, nullable=False)
    monthly_income = db.Column(db.Numeric(14, 2), nullable=False)
    employment_status = db.Column(db.String(20), nullable=False)
    years_employment = db.Column(db.Float, nullable=False)
    credit_score = db.Column(db.Integer, nullable=False)  # 300-850
    existing_debt = db.Column(db.Numeric(14, 2), nullable=False)
    dti_ratio = db.Column(db.Float, nullable=False)  # debt-to-income, percent
    loan_amount = db.Column(db.Numeric(14, 2), nullable=False)
    loan_term = db.Column(db.Integer, nullable=False)  # months
    previous_loans = db.Column(db.Integer, nullable=False, default=0)
    payment_history = db.Column(db.String(10), nullable=False)

    # Prediction.
    risk_label = db.Column(db.String(20), nullable=False)
    risk_percent = db.Column(db.Float, nullable=False)  # 0-100
    model_version = db.Column(db.String(30), nullable=True)

    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    client = db.relationship("Client", back_populates="credit_applications")
    user = db.relationship("User", back_populates="credit_applications")

    @validates("employment_status")
    def _validate_employment_status(self, key, value):
        return _require_choice(key, value, EMPLOYMENT_STATUSES)

    @validates("payment_history")
    def _validate_payment_history(self, key, value):
        return _require_choice(key, value, PAYMENT_HISTORIES)

    @validates("risk_label")
    def _validate_risk_label(self, key, value):
        return _require_choice(key, value, RISK_LABELS)
