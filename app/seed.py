"""Demo user and sample data, loaded only by ``flask seed-demo``."""
import secrets
from datetime import date
from decimal import Decimal

from .auth.services import DEMO_EMAIL, DEMO_USERNAME, get_demo_user
from .extensions import db
from .models import User
from .services import repository

DEMO_TRANSACTIONS = [
    {
        "type": "income",
        "amount": Decimal("2500000.00"),
        "date": date(2026, 11, 1),
        "category": "Salary",
        "description": "Monthly salary",
    },
    {
        "type": "expense",
        "amount": Decimal("850000.00"),
        "date": date(2026, 11, 2),
        "category": "Housing",
        "description": "Rent",
    },
    {
        "type": "expense",
        "amount": Decimal("120500.00"),
        "date": date(2026, 11, 4),
        "category": "Food",
        "description": "Groceries",
    },
]


def ensure_demo_user():
    """Return ``(user, created)``; the demo user is created if it does not exist.

    Its password is random and never shown, so nobody can log in as it: it only
    owns the data that the app shows while AUTH_ENABLED is False.
    """
    user = get_demo_user()
    if user is not None:
        return user, False
    user = User(username=DEMO_USERNAME, email=DEMO_EMAIL)
    user.set_password(secrets.token_urlsafe(32))
    db.session.add(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return user, True


def seed_demo():
    """Create the demo user and, if it has no transactions yet, the sample ones.

    Running it again never duplicates data. Returns what it did.
    """
    user, created = ensure_demo_user()
    added = 0
    if not repository.list_transactions(user.id):
        for transaction in DEMO_TRANSACTIONS:
            repository.save_transaction({**transaction, "user_id": user.id})
            added += 1
    return {"user_created": created, "transactions_added": added}
