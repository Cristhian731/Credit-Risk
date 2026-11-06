"""Data access layer.

Routes read and write data ONLY through the functions in this module, never
through the database directly. When the real database arrives, only this file
changes.

TODO(teammate A): replace with database queries. Keep the function names,
arguments and return values:
    * ``data`` arguments are dicts whose keys are column names from
      app/models.py (without ``id`` and ``created_at``).
    * Every function returns plain dicts with the same keys plus ``id``, so
      templates and routes do not depend on SQLAlchemy objects.
    * ``list_*`` functions return only the given user's records, newest first.

For now the records live in memory: they are lost when the server restarts
and are not shared between server processes.
"""
import copy
import itertools
import threading
from datetime import date
from decimal import Decimal

# Demo records shown while the app runs without a database. They belong to
# the demo user (id=1) used while AUTH_ENABLED is False.
DEMO_USER_ID = 1
DEMO_TRANSACTIONS = [
    {
        "type": "income",
        "amount": Decimal("2500000.00"),
        "date": date(2026, 11, 1),
        "category": "Salary",
        "description": "Monthly salary",
        "user_id": DEMO_USER_ID,
    },
    {
        "type": "expense",
        "amount": Decimal("850000.00"),
        "date": date(2026, 11, 2),
        "category": "Housing",
        "description": "Rent",
        "user_id": DEMO_USER_ID,
    },
    {
        "type": "expense",
        "amount": Decimal("120500.00"),
        "date": date(2026, 11, 4),
        "category": "Food",
        "description": "Groceries",
        "user_id": DEMO_USER_ID,
    },
]

_lock = threading.Lock()
_transactions = []
_credit_applications = []
_ids = itertools.count(1)


def _store(records, data):
    with _lock:
        record = {**copy.deepcopy(data), "id": next(_ids)}
        records.append(record)
        return copy.deepcopy(record)


def _list(records, user_id, sort_key):
    with _lock:
        mine = [copy.deepcopy(r) for r in records if r["user_id"] == user_id]
    return sorted(mine, key=sort_key, reverse=True)


# TODO(teammate A): replace with database queries
def save_transaction(data):
    """Save an income or expense.

    Args:
        data: Keys ``type``, ``amount``, ``date``, ``category``,
            ``description`` and ``user_id``.

    Returns:
        The saved record, including its ``id``.
    """
    return _store(_transactions, data)


# TODO(teammate A): replace with database queries
def list_transactions(user_id):
    """Return the user's transactions, newest date first."""
    return _list(_transactions, user_id, lambda r: (r["date"], r["id"]))


# TODO(teammate A): replace with database queries
def save_credit_application(data):
    """Save one credit evaluation.

    Args:
        data: The credit form fields (see ml.features.FEATURE_ORDER, with the
            text values of the choice fields), ``risk_label``,
            ``risk_percent``, ``client_id`` and ``user_id``.

    Returns:
        The saved record, including its ``id``.
    """
    return _store(_credit_applications, data)


# TODO(teammate A): replace with database queries
def list_credit_applications(user_id):
    """Return the user's credit evaluations, newest first."""
    return _list(_credit_applications, user_id, lambda r: r["id"])


# TODO(teammate A): remove together with the in-memory storage.
def reset(seed=True):
    """Empty the in-memory storage; with ``seed`` add the demo transactions."""
    global _ids
    with _lock:
        _transactions.clear()
        _credit_applications.clear()
        _ids = itertools.count(1)
    if seed:
        for transaction in DEMO_TRANSACTIONS:
            save_transaction(transaction)


reset()
