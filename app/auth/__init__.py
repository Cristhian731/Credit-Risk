"""Authentication blueprint (owned by teammate B)."""
from flask import Blueprint

bp = Blueprint("auth", __name__, url_prefix="/auth")

from . import routes  # noqa: E402,F401  (registers the routes on bp)
