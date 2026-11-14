"""Structured log of the predictions of the trained models (JSON lines), used for monitoring.

One line per prediction with the date, the model, its model_version, the nine inputs of the model,
the probability of default and the label. It never has the name or the document of the customer.
Even so it holds financial data of an applicant, so it is ignored by git, kept for a limited time
(``PREDICTION_LOG_RETENTION_DAYS``) and purged with ``flask --app run purge-prediction-log``.
A failure to write the log never breaks a prediction.
"""
import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

# The only keys of a log line: nothing that identifies the customer.
RECORD_KEYS = ("timestamp", "model", "model_version", "inputs", "probability", "label")


def _plain(value):
    """A JSON-friendly Python value (numpy numbers become int or float)."""
    return value.item() if hasattr(value, "item") else value


class PredictionLog:
    """Appends one JSON line per prediction to ``path`` (an empty path turns the log off)."""

    def __init__(self, path=""):
        self.path = path
        self._lock = threading.Lock()

    @property
    def enabled(self):
        return bool(self.path)

    def record(self, model, model_version, inputs, probability, label, now=None):
        """Write one prediction. Returns the record, or None if the log is off or could not be written."""
        if not self.enabled:
            return None
        record = {
            "timestamp": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model": model,
            "model_version": model_version,
            "inputs": {name: _plain(value) for name, value in inputs.items()},
            "probability": round(float(probability), 4),
            "label": label,
        }
        try:
            with self._lock:
                directory = os.path.dirname(self.path)
                if directory:
                    os.makedirs(directory, exist_ok=True)
                with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            log.warning("The prediction log could not be written: %s", self.path)
            return None
        return record

    def summary(self):
        """Number of predictions, first and last date, and counts by model and label (None if there is no log)."""
        if not self.enabled or not os.path.exists(self.path):
            return None
        total, first, last, by_label, by_model = 0, None, None, {}, {}
        for record in self._read():
            total += 1
            first = min(first or record["timestamp"], record["timestamp"])
            last = max(last or record["timestamp"], record["timestamp"])
            by_label[record["label"]] = by_label.get(record["label"], 0) + 1
            by_model[record["model"]] = by_model.get(record["model"], 0) + 1
        return {"predictions": total, "first": first, "last": last, "by_label": by_label, "by_model": by_model}

    def _read(self):
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except ValueError:
                        continue

    def purge(self, days, now=None):
        """Delete the predictions older than ``days`` days. Returns ``(deleted, kept)``."""
        if not self.enabled or not os.path.exists(self.path):
            return 0, 0
        limit = (now or datetime.now(timezone.utc)) - timedelta(days=days)
        cutoff = limit.strftime("%Y-%m-%dT%H:%M:%SZ")
        kept, deleted = [], 0
        with self._lock:
            for record in self._read():
                if record["timestamp"] >= cutoff:
                    kept.append(record)
                else:
                    deleted += 1
            with open(self.path, "w", encoding="utf-8", newline="\n") as fh:
                for record in kept:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return deleted, len(kept)
