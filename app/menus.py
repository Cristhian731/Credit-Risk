"""Menus of the application: one public menu and one private menu per role.

The base template renders them, so the pages of each role are listed in one place. An item is
(endpoint, label). The private menu is shown in a sidebar; the public menu stays in the top bar.
"""
from .models import ROLES

# Methodology is a dropdown of its own in the top bar.
PUBLIC_MENU = (
    ("main.index", "Home"),
    ("credit.models", "Models"),
    ("main.resources", "Resources"),
)

_STAFF = (
    ("reviews.queue", "Review queue"),
    ("reviews.history", "Decisions history"),
    ("reviews.indicators", "Indicators"),
    ("credit.models", "Model testing"),
)

MENU_BY_ROLE = {
    "applicant": (
        ("dashboard.index", "Dashboard"),
        ("transactions.index", "My finances"),
        ("credit.index", "New request"),
        ("credit.history", "My requests"),
    ),
    "analyst": _STAFF,
    "admin": (
        ("admin.users", "Users and roles"),
        ("admin.categories", "Categories"),
        ("admin.monitoring", "Monitoring"),
        ("admin.reports", "Reports"),
    )
    + _STAFF,
}

assert set(MENU_BY_ROLE) == set(ROLES)


def private_menu(user):
    """The sidebar items of ``user`` (empty without a user)."""
    if user is None:
        return ()
    return MENU_BY_ROLE.get(user.role, ())
