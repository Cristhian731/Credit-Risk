"""Data access layer.

Routes read and write data ONLY through the functions in this module, never
through the database directly.

Contract:
    * ``data`` arguments are dicts; every function returns plain dicts (never
      SQLAlchemy objects), so templates and routes do not depend on the ORM.
    * ``list_*`` functions return only the given user's records, newest first.
    * Transactions carry the category as text (``category``); the category row
      is created the first time a user uses it, per user and type.
    * A credit application carries the customer as ``client_full_name`` and
      ``client_document``; the client is looked up by document within the user
      and created when it is new.
    * Nothing calculable is stored: totals and balances are computed on read.
    * ``get_*``, ``update_*`` and ``delete_*`` take the ``user_id`` first and
      only touch that user's records: another user's id behaves exactly like
      a missing one (None / False), so callers can answer 404 for both.
    * Transactions can be edited and deleted; credit evaluations can only be
      deleted. Categories and clients left unused are kept.

Each ``save_*``, ``update_*`` and ``delete_*`` function commits; if anything fails the session is rolled back
and the error is raised again.
"""
import unicodedata
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Category, Client, CreditApplication, Transaction

# Columns of credit_applications that come straight from the evaluation form.
_APPLICATION_FIELDS = (
    "age", "monthly_income", "employment_status", "years_employment", "credit_score",
    "existing_debt", "dti_ratio", "loan_amount", "loan_term", "previous_loans",
    "payment_history", "risk_label", "risk_percent", "model_version",
)


def _get_or_create(select_existing, create):
    """Return the row ``select_existing`` finds, creating it once if it is missing.

    ``create`` returns a new, not yet added, row. If another request creates the
    same row first, the unique constraint raises and the winner's row is used.
    """
    existing = db.session.execute(select_existing).scalar_one_or_none()
    if existing is not None:
        return existing
    row = create()
    db.session.add(row)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return db.session.execute(select_existing).scalar_one()
    return row


def _category(user_id, name, kind):
    name = name.strip()
    return _get_or_create(
        db.select(Category).where(
            Category.user_id == user_id,
            Category.type == kind,
            func.lower(Category.name) == name.lower(),
        ),
        lambda: Category(name=name, type=kind, user_id=user_id),
    )


def _client(user_id, full_name, document):
    document = " ".join(document.split())
    full_name = " ".join(full_name.split())
    client = _get_or_create(
        db.select(Client).where(
            Client.user_id == user_id,
            func.lower(Client.document_number) == document.lower(),
        ),
        lambda: Client(full_name=full_name, document_number=document, user_id=user_id),
    )
    if client.full_name != full_name:  # the latest spelling of the name wins
        client.full_name = full_name
    return client


def _transaction_dict(transaction):
    return {
        "id": transaction.id,
        "type": transaction.type,
        "amount": transaction.amount,
        "date": transaction.date,
        "category": transaction.category.name,
        "description": transaction.description or "",
        "user_id": transaction.user_id,
    }


def _application_dict(application):
    record = {field: getattr(application, field) for field in _APPLICATION_FIELDS}
    record.update(
        id=application.id,
        client_id=application.client_id,
        client_full_name=application.client.full_name,
        client_document=application.client.document_number,
        user_id=application.user_id,
        created_at=application.created_at,
    )
    return record


def save_transaction(data):
    """Save an income or expense.

    Args:
        data: Keys ``type``, ``amount``, ``date``, ``category``,
            ``description`` and ``user_id``.

    Returns:
        The saved record, including its ``id``.
    """
    try:
        category = _category(data["user_id"], data["category"], data["type"])
        transaction = Transaction(
            type=data["type"],
            amount=data["amount"],
            date=data["date"],
            description=data.get("description") or None,
            category=category,
            user_id=data["user_id"],
        )
        db.session.add(transaction)
        db.session.commit()
        return _transaction_dict(transaction)
    except Exception:
        db.session.rollback()
        raise


def list_transactions(user_id):
    """Return the user's transactions, newest date first."""
    rows = db.session.execute(
        db.select(Transaction)
        .options(joinedload(Transaction.category))
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
    ).scalars()
    return [_transaction_dict(row) for row in rows]


def save_credit_application(data):
    """Save one credit evaluation.

    Args:
        data: The credit form fields (see ml.features.FEATURE_ORDER, with the
            text values of the choice fields), ``risk_label``,
            ``risk_percent``, ``client_full_name``, ``client_document`` and
            ``user_id``.

    Returns:
        The saved record, including its ``id`` and ``client_id``.
    """
    try:
        client = _client(data["user_id"], data["client_full_name"], data["client_document"])
        application = CreditApplication(
            **{field: data[field] for field in _APPLICATION_FIELDS if field in data},
            client=client,
            user_id=data["user_id"],
        )
        db.session.add(application)
        db.session.commit()
        return _application_dict(application)
    except Exception:
        db.session.rollback()
        raise


def list_credit_applications(user_id, limit=None):
    """Return the user's credit evaluations, newest first (at most ``limit``)."""
    query = (
        db.select(CreditApplication)
        .options(joinedload(CreditApplication.client))
        .where(CreditApplication.user_id == user_id)
        .order_by(CreditApplication.id.desc())
    )
    if limit is not None:
        query = query.limit(limit)
    return [_application_dict(row) for row in db.session.execute(query).scalars()]


def count_credit_applications(user_id):
    """Return how many evaluations the user has made."""
    return db.session.execute(
        db.select(func.count(CreditApplication.id)).where(CreditApplication.user_id == user_id)
    ).scalar_one()


def _own_transaction(user_id, transaction_id):
    """The transaction if it exists and belongs to the user, otherwise None."""
    return db.session.execute(
        db.select(Transaction)
        .options(joinedload(Transaction.category))
        .where(Transaction.id == transaction_id, Transaction.user_id == user_id)
    ).scalar_one_or_none()


def _own_credit_application(user_id, application_id):
    """The evaluation if it exists and belongs to the user, otherwise None."""
    return db.session.execute(
        db.select(CreditApplication)
        .options(joinedload(CreditApplication.client))
        .where(CreditApplication.id == application_id, CreditApplication.user_id == user_id)
    ).scalar_one_or_none()


def get_transaction(user_id, transaction_id):
    """Return the user's transaction, or None if it does not exist or is someone else's."""
    transaction = _own_transaction(user_id, transaction_id)
    return None if transaction is None else _transaction_dict(transaction)


def update_transaction(user_id, transaction_id, data):
    """Replace the fields of one of the user's transactions.

    Args:
        data: Same keys as ``save_transaction`` except ``user_id``. A new
            category is created on first use; the previous one is kept even if
            no transaction uses it any more.

    Returns:
        The updated record, or None if the transaction is not the user's.
    """
    try:
        transaction = _own_transaction(user_id, transaction_id)
        if transaction is None:
            return None
        transaction.category = _category(user_id, data["category"], data["type"])
        transaction.type = data["type"]
        transaction.amount = data["amount"]
        transaction.date = data["date"]
        transaction.description = data.get("description") or None
        db.session.commit()
        return _transaction_dict(transaction)
    except Exception:
        db.session.rollback()
        raise


def delete_transaction(user_id, transaction_id):
    """Delete one of the user's transactions; its category is kept.

    Returns:
        True if it was deleted, False if it is not the user's.
    """
    try:
        transaction = _own_transaction(user_id, transaction_id)
        if transaction is None:
            return False
        db.session.delete(transaction)
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        raise


def get_credit_application(user_id, application_id):
    """Return the user's evaluation, or None if it does not exist or is someone else's."""
    application = _own_credit_application(user_id, application_id)
    return None if application is None else _application_dict(application)


def delete_credit_application(user_id, application_id):
    """Delete one of the user's evaluations (they are never edited); the client is kept.

    Returns:
        True if it was deleted, False if it is not the user's.
    """
    try:
        application = _own_credit_application(user_id, application_id)
        if application is None:
            return False
        db.session.delete(application)
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        raise


def _paginate(rows_query, count_query, page, per_page, to_dict):
    """One page of results, cut by the database (LIMIT/OFFSET), never in Python.

    ``page`` is clamped: anything below 1 or not an integer becomes 1, and a
    page past the end becomes the last page. An empty list has one empty page.
    """
    total = db.session.execute(count_query).scalar_one()
    pages = max(1, -(-total // per_page))
    page = page if isinstance(page, int) and not isinstance(page, bool) else 1
    page = min(max(page, 1), pages)
    rows = db.session.execute(rows_query.limit(per_page).offset((page - 1) * per_page)).scalars()
    return {
        "items": [to_dict(row) for row in rows],
        "page": page,
        "pages": pages,
        "total": total,
        "per_page": per_page,
    }


def paginate_transactions(user_id, page, per_page):
    """One page of the user's transactions, in the same order as ``list_transactions``.

    Returns:
        A dict with ``items`` (plain dicts), ``page``, ``pages``, ``total`` and ``per_page``.
    """
    return _paginate(
        db.select(Transaction)
        .options(joinedload(Transaction.category))
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.date.desc(), Transaction.id.desc()),
        db.select(func.count(Transaction.id)).where(Transaction.user_id == user_id),
        page, per_page, _transaction_dict,
    )


def paginate_credit_applications(user_id, page, per_page):
    """One page of the user's evaluations, newest first. Same shape as ``paginate_transactions``."""
    return _paginate(
        db.select(CreditApplication)
        .options(joinedload(CreditApplication.client))
        .where(CreditApplication.user_id == user_id)
        .order_by(CreditApplication.id.desc()),
        db.select(func.count(CreditApplication.id)).where(CreditApplication.user_id == user_id),
        page, per_page, _application_dict,
    )


def transaction_totals(user_id):
    """Income, expense and balance over ALL the user's transactions, summed by the database.

    Nothing is stored: the totals are calculated every time they are read.
    """
    sums = dict(
        db.session.execute(
            db.select(Transaction.type, func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.user_id == user_id)
            .group_by(Transaction.type)
        ).all()
    )
    cents = Decimal("0.01")
    income = Decimal(str(sums.get("income", 0))).quantize(cents)
    expense = Decimal(str(sums.get("expense", 0))).quantize(cents)
    return {"income": income, "expense": expense, "balance": income - expense}


# ---------------------------------------------------------------------------
# Link between the finance module and the credit evaluation (calculated on read, never stored).
# ---------------------------------------------------------------------------

INCOME_MONTHS = 3
LOOKBACK_MONTHS = 12
# Expense categories whose name contains one of these words (ignoring case and accents) are
# suggested as debt payments. The user adjusts the selection; nothing is stored.
DEBT_KEYWORDS = ("loan", "credit", "debt", "prestamo", "tarjeta", "deuda")


def _plain(text):
    """Lowercase text without accents, to compare category names."""
    return "".join(
        char for char in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(char)
    )


def is_debt_category_name(name):
    """True if a category name suggests a debt payment (loan, credit, debt, prestamo, tarjeta, deuda)."""
    return any(word in _plain(name) for word in DEBT_KEYWORDS)


def _month_shift(first_day, months):
    """First day of the month ``months`` months after ``first_day`` (negative: before)."""
    index = first_day.year * 12 + (first_day.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def finance_summary_for_credit(user_id, debt_category_ids=None, today=None):
    """Monthly income and debt-to-income ratio of a user, calculated from their transactions.

    Nothing is stored: the values are calculated every time they are read.

    * Monthly income: the average of the monthly income totals of the (up to) 3 most recent
      COMPLETE calendar months that have at least one income, looking back 12 months from the
      current month. The current month is never used.
    * Debt payments: the expenses of the chosen categories, averaged over those same months.
    * DTI: debt payments divided by the monthly income, in percent (capped at 100, which is
      what the credit form accepts).

    Args:
        user_id: Only this user's transactions and categories are read.
        debt_category_ids: Ids of expense categories that are debt payments. Ids that are not the
            user's expense categories are ignored. ``None`` selects the suggested categories
            (``is_debt_category_name``); an empty list selects none.
        today: Reference date (default: today), to make the calculation testable.

    Returns:
        A dict with ``monthly_income`` (Decimal or None), ``months`` (the months used, newest
        first, as ``{"key": "2026-10", "label": "October 2026"}``), ``debt_monthly``, ``dti_percent``
        (None without income or without selected categories), ``dti_capped``,
        ``expense_categories`` (``id``, ``name``, ``suggested``, ``selected``) and ``selected_names``.
    """
    today = today or date.today()
    current = today.replace(day=1)
    window_start = _month_shift(current, -LOOKBACK_MONTHS)
    cents = Decimal("0.01")

    income_by_month = {}
    for when, amount in db.session.execute(
        db.select(Transaction.date, Transaction.amount).where(
            Transaction.user_id == user_id,
            Transaction.type == "income",
            Transaction.date >= window_start,
            Transaction.date < current,
        )
    ):
        key = (when.year, when.month)
        income_by_month[key] = income_by_month.get(key, Decimal(0)) + Decimal(str(amount))

    used = sorted(income_by_month, reverse=True)[:INCOME_MONTHS]
    monthly_income = None
    if used:
        monthly_income = (sum(income_by_month[key] for key in used) / len(used)).quantize(cents, ROUND_HALF_UP)

    categories = [
        {"id": row.id, "name": row.name, "suggested": is_debt_category_name(row.name)}
        for row in db.session.execute(
            db.select(Category).where(Category.user_id == user_id, Category.type == "expense").order_by(Category.name)
        ).scalars()
    ]
    own_ids = {item["id"] for item in categories}
    if debt_category_ids is None:
        selected = {item["id"] for item in categories if item["suggested"]}
    else:
        selected = {int(value) for value in debt_category_ids} & own_ids
    for item in categories:
        item["selected"] = item["id"] in selected

    debt_monthly, dti_percent, dti_capped = None, None, False
    if used and selected:
        total = Decimal(0)
        for when, amount in db.session.execute(
            db.select(Transaction.date, Transaction.amount).where(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
                Transaction.category_id.in_(selected),
                Transaction.date >= window_start,
                Transaction.date < current,
            )
        ):
            if (when.year, when.month) in used:
                total += Decimal(str(amount))
        debt_monthly = (total / len(used)).quantize(cents, ROUND_HALF_UP)
        if monthly_income:
            ratio = (debt_monthly / monthly_income * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
            dti_capped = ratio > 100
            dti_percent = float(min(ratio, Decimal(100)))

    return {
        "monthly_income": monthly_income,
        "months": [{"key": f"{y}-{m:02d}", "label": date(y, m, 1).strftime("%B %Y")} for y, m in used],
        "debt_monthly": debt_monthly,
        "dti_percent": dti_percent,
        "dti_capped": dti_capped,
        "expense_categories": categories,
        "selected_names": [item["name"] for item in categories if item["selected"]],
    }
