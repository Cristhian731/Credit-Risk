"""Financial summary dashboard blueprint."""
from flask import Blueprint

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

from . import routes  # noqa: E402,F401  (registers the routes on bp)
