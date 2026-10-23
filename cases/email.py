from typing import TYPE_CHECKING

from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _

from governanceplatform.email import send_html_email

if TYPE_CHECKING:
    from django.http import HttpRequest

    from .models import Case, CaseMessage


def _case_url(request: HttpRequest, case: Case) -> str:
    return request.build_absolute_uri(reverse("case_detail", args=[case.reference]))


def send_case_submitted_emails(request: HttpRequest, case: Case) -> None:
    context = {"case": case, "case_url": _case_url(request, case)}
    send_html_email(
        _("Your case %(reference)s has been received") % {"reference": case.reference},
        render_to_string("cases/emails/case_submitted.html", context),
        [case.submitter_email],
    )
    if case.regulator.email_for_notification:
        send_html_email(
            _("New case %(reference)s") % {"reference": case.reference},
            render_to_string("cases/emails/case_new_for_regulator.html", context),
            [case.regulator.email_for_notification],
        )


def send_case_message_email(request: HttpRequest, message: CaseMessage) -> None:
    """Tells the other side of the case that something was added to it."""
    case = message.case
    recipient = case.submitter_email if message.is_from_regulator else case.regulator.email_for_notification
    if not recipient:
        return
    send_html_email(
        _("Update on case %(reference)s") % {"reference": case.reference},
        render_to_string(
            "cases/emails/case_message.html",
            {"case": case, "message": message, "case_url": _case_url(request, case)},
        ),
        [recipient],
    )
