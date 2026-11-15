"""Business rules of the credit request flow, as pure functions (no database, easy to test).

The numbers BR4 to BR7 refer to docs/SYSTEM_DESIGN.md.
"""
from ..models import (
    STATUS_APPROVED,
    STATUS_DOCUMENTS,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_WITHDRAWN,
)

JUSTIFICATION_MIN = 10
JUSTIFICATION_MAX = 1000
YOUNG_AGE_RANGE = (18, 24)

# Statuses in which the applicant can still edit or withdraw the request.
OPEN_STATUSES = (STATUS_PENDING, STATUS_DOCUMENTS)
# Statuses in which the applicant can delete the request (nothing was decided about it).
DELETABLE_STATUSES = (STATUS_PENDING, STATUS_WITHDRAWN)

HUMAN_REVIEW_NOTE = "Human review confirmed."


def is_young(age):
    return YOUNG_AGE_RANGE[0] <= age <= YOUNG_AGE_RANGE[1]


def is_mandatory_review(risk_label, age):
    """BR4: High Risk or an applicant aged 18 to 24 must be reviewed (all requests are, but these go first)."""
    return risk_label == "High Risk" or is_young(age)


def followed_model(risk_label, decision):
    """BR7: True or False when the model gave a clear recommendation, None when it did not.

    Low risk (label "Approved") with Approve and High Risk with Reject follow the model; the opposite
    pairs contradict it. Medium Risk and Request documents have no clear recommendation.
    """
    if decision == STATUS_DOCUMENTS or risk_label == "Medium Risk":
        return None
    expected = STATUS_APPROVED if risk_label == "Approved" else STATUS_REJECTED
    return decision == expected


def validate_decision(decision, justification, age, human_review):
    """BR4 and BR5. Returns ``(clean_justification, errors)``."""
    errors = []
    text = " ".join((justification or "").split())
    if decision not in (STATUS_APPROVED, STATUS_REJECTED, STATUS_DOCUMENTS):
        errors.append("Choose Approve, Reject or Request documents.")
    if len(text) < JUSTIFICATION_MIN:
        errors.append(f"The justification needs at least {JUSTIFICATION_MIN} characters.")
    elif len(text) > JUSTIFICATION_MAX:
        errors.append(f"The justification can have at most {JUSTIFICATION_MAX} characters.")
    if decision == STATUS_REJECTED and is_young(age):
        if not human_review:
            errors.append("Rejecting an applicant aged 18 to 24 requires confirming the human review.")
        else:
            text = f"{HUMAN_REVIEW_NOTE} {text}"
    return text, errors


def can_applicant_edit(status):
    return status in OPEN_STATUSES


def can_applicant_delete(status):
    return status in DELETABLE_STATUSES


def can_record_outcome(status, outcome):
    """BR6: only Approved requests, only once."""
    return status == STATUS_APPROVED and outcome is None


def review_priority(risk_label, age):
    """Sort key part of the queue: 0 = mandatory review first, 1 = the rest."""
    return 0 if is_mandatory_review(risk_label, age) else 1
