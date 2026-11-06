"""Income and expense transactions blueprint."""
from flask import Blueprint

bp = Blueprint("transactions", __name__, url_prefix="/transactions")

from . import routes  # noqa: E402,F401  (registers the routes on bp)
