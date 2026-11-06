"""Validation for the income and expense form."""
from datetime import date
from decimal import Decimal, InvalidOperation

from ..models import TRANSACTION_TYPES

MAX_AMOUNT = Decimal("1000000000000")


def validate_transaction(form):
    """Validate the submitted transaction form.

    Args:
        form: A mapping such as ``request.form`` with the fields ``type``,
            ``amount``, ``date``, ``category`` and ``description``.

    Returns:
        ``(clean_values, errors)``: typed values keyed by field name and a
        list of human-readable error messages.
    """
    clean, errors = {}, []

    kind = (form.get("type") or "").strip().lower()
    if kind in TRANSACTION_TYPES:
        clean["type"] = kind
    else:
        errors.append("Type must be income or expense.")

    try:
        amount = Decimal((form.get("amount") or "").strip())
        if not (0 < amount < MAX_AMOUNT) or amount != amount.quantize(Decimal("0.01")):
            raise InvalidOperation
        clean["amount"] = amount
    except InvalidOperation:
        errors.append("Amount must be a positive number with at most two decimals.")

    try:
        clean["date"] = date.fromisoformat((form.get("date") or "").strip())
    except ValueError:
        errors.append("Date must be a valid date.")

    category = (form.get("category") or "").strip()
    if 0 < len(category) <= 50:
        clean["category"] = category
    else:
        errors.append("Category is required (at most 50 characters).")

    description = (form.get("description") or "").strip()
    if len(description) <= 255:
        clean["description"] = description
    else:
        errors.append("Description must have at most 255 characters.")

    return clean, errors
