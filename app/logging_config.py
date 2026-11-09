"""Application logging: one stream handler and an optional rotating file."""
import logging
from logging.handlers import RotatingFileHandler

from flask.logging import default_handler

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_HANDLER_FLAG = "_credit_risk_handler"


def configure_logging(app):
    """Attach the project's handlers to ``app.logger``.

    Reads ``LOG_LEVEL`` (default INFO) and, when set, ``LOG_FILE``. Calling it
    again for another app never duplicates handlers.
    """
    logger = app.logger
    logger.removeHandler(default_handler)
    for handler in [h for h in logger.handlers if getattr(h, _HANDLER_FLAG, False)]:
        logger.removeHandler(handler)
        handler.close()

    handlers = [logging.StreamHandler()]
    log_file = app.config.get("LOG_FILE")
    if log_file:
        handlers.append(RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"))

    formatter = logging.Formatter(LOG_FORMAT)
    for handler in handlers:
        handler.setFormatter(formatter)
        setattr(handler, _HANDLER_FLAG, True)
        logger.addHandler(handler)

    logger.setLevel(app.config.get("LOG_LEVEL", "INFO").upper())
