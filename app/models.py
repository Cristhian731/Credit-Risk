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


# TODO(teammate A): inherit from db.Model and implement the fields below.
class User:
    """A registered person who owns categories, transactions and budgets.

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
