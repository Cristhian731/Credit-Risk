"""Database model contracts for Credit Risk.

TODO(teammate A): turn each template below into a Flask-SQLAlchemy model.

Rules of the contract:
    * Every model inherits from ``db.Model`` (``from app.extensions import db``).
    * Class names, table names, column names and relationship names must stay
      exactly as documented here; other modules and the tests depend on them.
    * "required" means ``nullable=False``.
    * Relationships are declared on both sides with ``back_populates``.
    * Do not call ``db.create_all()`` at import time.

The contract is fulfilled when ``tests/test_models_contract.py`` passes
without its ``xfail`` marker.
"""

# Allowed values for Category.type and Transaction.type.
TRANSACTION_TYPES = ("income", "expense")

# Allowed values for CreditApplication text columns. They match the option
# values of the credit form and the encodings in ml/features.py.
EMPLOYMENT_STATUSES = ("employed", "self_employed", "retired", "unemployed")
PAYMENT_HISTORIES = ("good", "fair", "poor")
RISK_LABELS = ("Approved", "Medium Risk", "High Risk")


# TODO(teammate A): inherit from db.Model and implement the fields below.
class User:
    """A registered person who owns finances, clients and credit applications.

    Table: ``users``

    Columns:
        id (Integer): primary key.
        username (String(80)): required, unique.
        email (String(120)): required, unique.
        password_hash (String(255)): required. Stores a hash, never the plain
            password (see app/auth/services.py).
        created_at (DateTime): required, defaults to the current UTC time.

    Relationships:
        categories (list[Category]): back_populates="user".
        transactions (list[Transaction]): back_populates="user".
        budgets (list[Budget]): back_populates="user".
        clients (list[Client]): back_populates="user".
        credit_applications (list[CreditApplication]): back_populates="user".
    """

    __tablename__ = "users"


# TODO(teammate A): inherit from db.Model and implement the fields below.
class Category:
    """A label that groups transactions, e.g. "Food" or "Salary".

    Table: ``categories``

    Columns:
        id (Integer): primary key.
        name (String(50)): required.
        type (String(10)): required, one of TRANSACTION_TYPES.
        user_id (Integer): required, foreign key to ``users.id``.

    Relationships:
        user (User): back_populates="categories".
        transactions (list[Transaction]): back_populates="category".
        budgets (list[Budget]): back_populates="category".
    """

    __tablename__ = "categories"


# TODO(teammate A): inherit from db.Model and implement the fields below.
class Transaction:
    """A single income or expense recorded by a user.

    Table: ``transactions``

    Columns:
        id (Integer): primary key.
        type (String(10)): required, one of TRANSACTION_TYPES. Any other
            value must be rejected (validator or CHECK constraint).
        amount (Numeric(12, 2)): required.
        date (Date): required.
        category_id (Integer): required, foreign key to ``categories.id``.
        description (String(255)): optional.
        user_id (Integer): required, foreign key to ``users.id``.

    Relationships:
        user (User): back_populates="transactions".
        category (Category): back_populates="transactions".
    """

    __tablename__ = "transactions"


# TODO(teammate A): inherit from db.Model and implement the fields below.
class Budget:
    """A spending limit for one category in one month.

    Table: ``budgets``

    Columns:
        id (Integer): primary key.
        amount (Numeric(12, 2)): required, the monthly limit.
        month (Date): required, the first day of the budgeted month.
        category_id (Integer): required, foreign key to ``categories.id``.
        user_id (Integer): required, foreign key to ``users.id``.

    Relationships:
        user (User): back_populates="budgets".
        category (Category): back_populates="budgets".
    """

    __tablename__ = "budgets"


# TODO(teammate A): inherit from db.Model and implement the fields below.
class Client:
    """A customer whose loan applications are evaluated.

    Table: ``clients``

    Columns:
        id (Integer): primary key.
        full_name (String(120)): required.
        document_number (String(30)): required, unique. National ID or similar.
        user_id (Integer): required, foreign key to ``users.id``; the user who
            registered the client.
        created_at (DateTime): required, defaults to the current UTC time.

    Relationships:
        user (User): back_populates="clients".
        credit_applications (list[CreditApplication]): back_populates="client".
    """

    __tablename__ = "clients"


# TODO(teammate A): inherit from db.Model and implement the fields below.
class CreditApplication:
    """One loan evaluation: the customer data at that moment and the prediction.

    The feature columns use exactly the names of the credit form fields and of
    ``ml.features.FEATURE_ORDER``.

    Table: ``credit_applications``

    Columns:
        id (Integer): primary key.
        age (Integer): required.
        monthly_income (Numeric(14, 2)): required.
        employment_status (String(20)): required, one of EMPLOYMENT_STATUSES.
        years_employment (Float): required.
        credit_score (Integer): required.
        existing_debt (Numeric(14, 2)): required.
        dti_ratio (Float): required, debt-to-income ratio in percent.
        loan_amount (Numeric(14, 2)): required.
        loan_term (Integer): required, in months.
        previous_loans (Integer): required.
        payment_history (String(10)): required, one of PAYMENT_HISTORIES.
        risk_label (String(20)): required, one of RISK_LABELS.
        risk_percent (Float): required, estimated default risk from 0 to 100.
        client_id (Integer): required, foreign key to ``clients.id``.
        user_id (Integer): required, foreign key to ``users.id``; the user who
            ran the evaluation.
        created_at (DateTime): required, defaults to the current UTC time.

    Relationships:
        client (Client): back_populates="credit_applications".
        user (User): back_populates="credit_applications".
    """

    __tablename__ = "credit_applications"
