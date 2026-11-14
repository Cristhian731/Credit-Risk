"""Administrator pages: users and roles, categories, monitoring and reports."""
from flask import Blueprint

bp = Blueprint("admin", __name__, url_prefix="/admin")

from . import routes  # noqa: E402,F401  (registers the routes on bp)
