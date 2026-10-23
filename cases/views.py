from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django_otp.decorators import otp_required

from governanceplatform.decorators import check_user_is_correct
from governanceplatform.helpers import get_active_company_from_session

from .email import send_case_message_email, send_case_submitted_emails
from .forms import CaseReplyForm, CaseReviewForm, CaseSubmissionForm
from .globals import CASE_STATUS, CASE_STATUS_DISPLAY
from .models import Case, CaseAnswer, CaseForm, CaseMessage


def can_submit_cases(user) -> bool:
    return not (user.is_regulator() or user.is_observer() or user.in_group("PlatformAdmin"))


def get_visible_case(request: HttpRequest, reference: str) -> Case:
    return get_object_or_404(
        Case.objects.visible_to(request.user).select_related("form", "regulator", "company"),
        reference=reference,
    )


@login_required
@otp_required
@check_user_is_correct
def get_cases(request: HttpRequest) -> HttpResponse:
    user = request.user
    if user.in_group("PlatformAdmin"):
        return redirect("admin:index")
    if user.is_observer():
        raise Http404()

    cases = Case.objects.visible_to(user).select_related("form", "form__regulation", "regulator", "company")
    counts = cases.aggregate(**{code: Count("id", filter=Q(status=code)) for code, _label in CASE_STATUS})

    status = request.GET.get("status", "")
    if status in dict(CASE_STATUS):
        cases = cases.filter(status=status)
    search = request.GET.get("search", "").strip()
    if search:
        cases = cases.filter(Q(reference__icontains=search) | Q(submitter_name__icontains=search) | Q(company__name__icontains=search))

    return render(
        request,
        "cases/dashboard.html",
        {
            "cases": cases,
            "status_tabs": [(code, label, counts[code]) for code, label in CASE_STATUS],
            "selected_status": status,
            "search": search,
            "status_display": CASE_STATUS_DISPLAY,
            "can_submit": can_submit_cases(user),
        },
    )


@login_required
@otp_required
@check_user_is_correct
def choose_case_form(request: HttpRequest) -> HttpResponse:
    if not can_submit_cases(request.user):
        raise Http404()
    case_forms = (
        CaseForm.objects.filter(is_active=True, form_questions__isnull=False, creator__isnull=False)
        .select_related("regulation", "creator")
        .distinct()
    )
    return render(request, "cases/choose_form.html", {"case_forms": case_forms, "can_submit": True})


@login_required
@otp_required
@check_user_is_correct
@require_http_methods(["GET", "POST"])
def create_case(request: HttpRequest, form_id: int) -> HttpResponse:
    user = request.user
    if not can_submit_cases(user):
        raise Http404()
    case_form = get_object_or_404(
        CaseForm.objects.select_related("regulation", "creator"),
        pk=form_id,
        is_active=True,
        creator__isnull=False,
    )

    form = CaseSubmissionForm(request.POST or None, request.FILES or None, case_form=case_form)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            case = Case.objects.create(
                form=case_form,
                regulator=case_form.creator,
                submitter=user,
                submitter_name=user.get_full_name() or user.email,
                submitter_email=user.email,
                company=get_active_company_from_session(request),
            )
            for form_question in form.form_questions:
                value = form.cleaned_data.get(form.field_name(form_question))
                answer = CaseAnswer.objects.create(
                    case=case,
                    question=form_question.question,
                    position=form_question.position,
                    answer="" if form_question.question.question_type in ("SO", "MULTI") or not value else str(value),
                )
                if form_question.question.question_type == "SO" and value:
                    answer.choices.set([value])
                elif form_question.question.question_type == "MULTI" and value:
                    answer.choices.set(value)
            CaseMessage.objects.create(
                case=case,
                author=user,
                author_name=case.submitter_name,
                status=case.status,
                attachment=form.cleaned_data.get("attachment") or "",
            )
        send_case_submitted_emails(request, case)
        messages.success(request, _("Your case has been submitted. Reference: %(reference)s") % {"reference": case.reference})
        return redirect("case_detail", reference=case.reference)

    return render(request, "cases/create.html", {"case_form": case_form, "form": form, "can_submit": True})


@login_required
@otp_required
@check_user_is_correct
@require_http_methods(["GET", "POST"])
def case_detail(request: HttpRequest, reference: str) -> HttpResponse:
    user = request.user
    case = get_visible_case(request, reference)
    is_regulator = user.is_regulator()

    # Only one side can act at a time, and nobody once the case is closed.
    form_class = None
    if is_regulator and case.status == "UNDER_REVIEW":
        form_class = CaseReviewForm
    elif not is_regulator and case.status == "REVISION_REQUIRED":
        form_class = CaseReplyForm

    if request.method == "POST":
        if form_class is None:
            raise Http404()
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                case.status = form.cleaned_data.get("decision", "UNDER_REVIEW")
                case.updated_at = timezone.now()
                case.save(update_fields=["status", "updated_at"])
                message = CaseMessage.objects.create(
                    case=case,
                    author=user,
                    author_name=user.get_full_name() or user.email,
                    is_from_regulator=is_regulator,
                    status=case.status,
                    text=form.cleaned_data["text"],
                    attachment=form.cleaned_data["attachment"] or "",
                )
            send_case_message_email(request, message)
            messages.success(request, _("The case has been updated."))
            return redirect("case_detail", reference=case.reference)
    else:
        form = form_class() if form_class else None

    iterations = case.iterations()
    current = iterations[-1]
    # The latest round: what the regulator asked last time, the submitter's answer, and the decision on it.
    latest_steps = [current.submission] if current.number > 1 else []
    if current.number > 1 and not current.feedback:
        latest_steps.insert(0, iterations[-2].feedback)
    if current.feedback:
        latest_steps.append(current.feedback)

    return render(
        request,
        "cases/detail.html",
        {
            "case": case,
            "answers": case.answers.select_related("question").prefetch_related("question__translations", "choices"),
            "submission": iterations[0].submission,
            "iterations": iterations,
            "latest_steps": latest_steps,
            "form": form,
            "status_display": CASE_STATUS_DISPLAY,
            "can_submit": can_submit_cases(user),
        },
    )


@login_required
@otp_required
@check_user_is_correct
def download_attachment(request: HttpRequest, reference: str, message_uuid: str) -> FileResponse:
    case = get_visible_case(request, reference)
    message = get_object_or_404(case.messages.exclude(attachment=""), uuid=message_uuid)
    return FileResponse(message.attachment.open("rb"), as_attachment=True, filename=message.attachment_name)
