"""Analyst pages: review queue, decisions history and indicators."""
from flask import Blueprint

bp = Blueprint("reviews", __name__, url_prefix="/reviews")

from . import routes  # noqa: E402,F401  (registers the routes on bp)
