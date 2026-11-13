"""Public Methodology pages: the overview and one page for each CRISP-ML phase."""
from flask import Blueprint

bp = Blueprint("methodology", __name__, url_prefix="/methodology")

from . import routes  # noqa: E402,F401  (registers the routes on bp)
