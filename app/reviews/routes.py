"""Analyst pages. The pages of the request flow arrive in block D3 and the indicators in D4.

Until then each page is a placeholder that already enforces the role, so the access rules can be
tested. ``PLACEHOLDER_ENDPOINTS`` lists them; tests/test_roles.py fails when any is left at the
end of D4.
"""
from flask import render_template

from ..auth.services import roles_required
from . import bp

PLACEHOLDER_ENDPOINTS = {"reviews.queue", "reviews.history", "reviews.indicators"}


def _placeholder(title, block):
    return render_template("placeholder.html", title=title, block=block)


@bp.route("/")
@roles_required("analyst", "admin")
def queue():
    """Review queue (block D3)."""
    return _placeholder("Review queue", "D3")


@bp.route("/history")
@roles_required("analyst", "admin")
def history():
    """Decisions history (block D3)."""
    return _placeholder("Decisions history", "D3")


@bp.route("/indicators")
@roles_required("analyst", "admin")
def indicators():
    """Indicators (block D4)."""
    return _placeholder("Indicators", "D4")
