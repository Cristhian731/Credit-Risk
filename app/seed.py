"""Demo user and sample data, loaded only by ``flask seed-demo``."""
import secrets
from datetime import date
from decimal import Decimal

from .auth.services import DEMO_EMAIL, DEMO_USERNAME, get_demo_user
from .extensions import db
from .models import User
from .services import repository

SAMPLE_LABEL = "Sample data"

# (type, category, description, amount in USD, day of the month) of each of the last 3 complete months.
_MONTHLY_PATTERN = (
    ("income", "Salary", "Monthly salary", Decimal("4200.00"), 1),
    ("expense", "Housing", "Rent", Decimal("900.00"), 3),
    ("expense", "Food", "Groceries", Decimal("350.00"), 6),
    ("expense", "Loan payment", "Personal loan installment", Decimal("600.00"), 10),
)
SAMPLE_MONTHS = 3


def demo_transactions(today=None):
    """Sample income and expenses of the 3 last COMPLETE months before ``today``, labeled "Sample data".

    The credit form takes the average of those months, so a fresh demo account fills the income and
    the debt-to-income ratio by itself. The "Loan payment" category is a suggested debt category.
    """
    today = today or date.today()
    year, month = today.year, today.month
    rows = []
    for _ in range(SAMPLE_MONTHS):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        for kind, category, description, amount, day in _MONTHLY_PATTERN:
            rows.append(
                {
                    "type": kind,
                    "amount": amount,
                    "date": date(year, month, day),
                    "category": category,
                    "description": f"{SAMPLE_LABEL}: {description}",
                }
            )
    return rows


def ensure_demo_user(password=None):
    """Return ``(user, created)``; the demo user is created if it does not exist.

    With ``password`` (``flask seed-demo`` passes ``DEMO_PASSWORD``) the demo account can log in with
    it, and running the command again sets it to the current value. Without it the password is
    random and never shown, so nobody can log in as the demo user: it only owns the data that the
    app shows while AUTH_ENABLED is False.
    """
    user = get_demo_user()
    if user is not None:
        # The demo account is public: it never keeps another role.
        user.role = "applicant"
        if password:
            user.set_password(password)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return user, False
    user = User(username=DEMO_USERNAME, email=DEMO_EMAIL)
    user.set_password(password or secrets.token_urlsafe(32))
    db.session.add(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return user, True


def seed_demo(password=None):
    """Create the demo user and, if it has no transactions yet, the sample ones.

    Running it again never duplicates data. Returns what it did.
    """
    user, created = ensure_demo_user(password)
    added = 0
    if not repository.list_transactions(user.id):
        for transaction in demo_transactions():
            repository.save_transaction({**transaction, "user_id": user.id})
            added += 1
    return {"user_created": created, "transactions_added": added}
