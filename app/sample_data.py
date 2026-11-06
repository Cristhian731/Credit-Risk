"""Hard-coded example data used by the placeholder routes.

Delete this module once the views read real data through app/models.py.
"""
from datetime import date
from decimal import Decimal

SAMPLE_TRANSACTIONS = [
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


def summarize(transactions):
    """Return total income, total expense and balance for a list of transactions."""
    income = sum((t["amount"] for t in transactions if t["type"] == "income"), Decimal("0"))
    expense = sum((t["amount"] for t in transactions if t["type"] == "expense"), Decimal("0"))
    return {"income": income, "expense": expense, "balance": income - expense}
