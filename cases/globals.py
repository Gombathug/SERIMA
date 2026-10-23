from django.utils.translation import gettext_lazy as _

# Marks a reference as a case of the case management module
REFERENCE_PREFIX = "CA_"

QUESTION_TYPES = [
    ("FREETEXT", _("Free text")),
    ("SO", _("Single choice")),
    ("MULTI", _("Multiple choice")),
    ("DATE", _("Date")),
]

CHOICE_QUESTION_TYPES = ["SO", "MULTI"]

# A case goes back to UNDER_REVIEW each time the submitter answers a revision request;
# CLOSED is final.
CASE_STATUS = [
    ("UNDER_REVIEW", _("Under review")),
    ("REVISION_REQUIRED", _("Revision required")),
    ("CLOSED", _("Closed")),
]

# what the regulator can decide on a case under review
REVIEW_DECISIONS = [choice for choice in CASE_STATUS if choice[0] != "UNDER_REVIEW"]

# css class and bootstrap icon of each status, in the dashboard and the case page
CASE_STATUS_DISPLAY = {
    "UNDER_REVIEW": ("text-bg-info", "bi-hourglass-split"),
    "REVISION_REQUIRED": ("text-bg-warning", "bi-pencil-square"),
    "CLOSED": ("text-bg-secondary", "bi-lock"),
}

# Files are kept off the static tree and only served by the permission-checked view,
# so the allowed types are limited to documents a person would attach to a complaint.
ATTACHMENT_EXTENSIONS = ["pdf", "png", "jpg", "jpeg", "txt", "csv", "docx", "xlsx", "odt", "ods"]
ATTACHMENT_MAX_SIZE = 10 * 1024 * 1024
