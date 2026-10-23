import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from cases.models import Case
from cases.tests.conftest import make_regulator


@pytest.fixture
def submitter(make_user):
    return make_user("citizen@example.org", "IncidentUser")


@pytest.fixture
def regulator_user(make_user, regulators):
    return make_user("reguser@ibpt.example.org", "RegulatorUser", regulator=regulators[0])


@pytest.fixture
def submitted_case(otp_client, submitter, case_form, submission_data):
    otp_client(submitter).post(reverse("create_case", args=[case_form.pk]), submission_data)
    return Case.objects.get()


@pytest.mark.django_db
def test_submitter_creates_case_with_answers(otp_client, submitter, case_form, submission_data):
    response = otp_client(submitter).post(reverse("create_case", args=[case_form.pk]), submission_data)

    case = Case.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("case_detail", args=[case.reference])
    assert case.regulator == case_form.creator
    assert case.status == "UNDER_REVIEW"
    assert [str(choice) for choice in case.answers.get(position=1).choices.all()] == ["Complaint"]
    assert case.answers.get(position=2).answer == "My complaint"


@pytest.mark.django_db
def test_submission_emails_submitter_and_regulator(submitted_case):
    recipients = [message.bcc for message in mail.outbox]
    assert recipients == [["citizen@example.org"], ["ibpt@example.org"]]


@pytest.mark.django_db
def test_missing_mandatory_answer_creates_no_case(otp_client, submitter, case_form, submission_data):
    request_type_field = next(iter(submission_data))
    del submission_data[request_type_field]

    response = otp_client(submitter).post(reverse("create_case", args=[case_form.pk]), submission_data)

    assert response.status_code == 200
    assert not Case.objects.exists()


@pytest.mark.django_db
def test_disallowed_attachment_type_is_rejected(otp_client, submitter, case_form, submission_data):
    submission_data["attachment"] = SimpleUploadedFile("script.exe", b"MZ")

    otp_client(submitter).post(reverse("create_case", args=[case_form.pk]), submission_data)

    assert not Case.objects.exists()


@pytest.mark.django_db
def test_other_submitter_cannot_open_case(otp_client, make_user, submitted_case):
    client = otp_client(make_user("someone-else@example.org", "IncidentUser"))

    assert client.get(reverse("case_detail", args=[submitted_case.reference])).status_code == 404
    assert submitted_case.reference not in client.get(reverse("cases")).content.decode()


@pytest.mark.django_db
def test_regulator_of_another_regulator_cannot_open_case(otp_client, make_user, submitted_case):
    other_regulator = make_regulator("Elsewhere")
    client = otp_client(make_user("reg@elsewhere.example.org", "RegulatorUser", regulator=other_regulator))

    assert client.get(reverse("case_detail", args=[submitted_case.reference])).status_code == 404


def review(client, case, decision, text="", **files):
    return client.post(reverse("case_detail", args=[case.reference]), {"decision": decision, "text": text, **files})


def reply(client, case, text):
    return client.post(reverse("case_detail", args=[case.reference]), {"text": text})


@pytest.mark.django_db
def test_submitter_cannot_comment_while_under_review(otp_client, submitter, submitted_case):
    response = reply(otp_client(submitter), submitted_case, "More info")

    assert response.status_code == 404
    assert not submitted_case.messages.filter(text="More info").exists()


@pytest.mark.django_db
def test_revision_request_needs_a_comment(otp_client, regulator_user, submitted_case):
    review(otp_client(regulator_user), submitted_case, "REVISION_REQUIRED")

    submitted_case.refresh_from_db()
    assert submitted_case.status == "UNDER_REVIEW"


@pytest.mark.django_db
def test_revision_request_with_file_reaches_submitter(otp_client, submitter, regulator_user, submitted_case):
    mail.outbox.clear()

    review(
        otp_client(regulator_user),
        submitted_case,
        "REVISION_REQUIRED",
        "Please add the dates.",
        attachment=SimpleUploadedFile("request.pdf", b"%PDF-1.4"),
    )

    submitted_case.refresh_from_db()
    feedback = submitted_case.messages.get(text="Please add the dates.")
    assert submitted_case.status == "REVISION_REQUIRED"
    assert feedback.is_from_regulator
    assert mail.outbox[0].bcc == ["citizen@example.org"]
    download = otp_client(submitter).get(reverse("case_attachment", args=[submitted_case.reference, feedback.uuid]))
    assert b"".join(download.streaming_content) == b"%PDF-1.4"


@pytest.mark.django_db
def test_submitter_answer_sends_case_back_under_review(otp_client, submitter, regulator_user, submitted_case):
    review(otp_client(regulator_user), submitted_case, "REVISION_REQUIRED", "Please add the dates.")

    reply(otp_client(submitter), submitted_case, "It happened on 1 October.")

    submitted_case.refresh_from_db()
    assert submitted_case.status == "UNDER_REVIEW"
    assert submitted_case.messages.filter(text="It happened on 1 October.", is_from_regulator=False).exists()


@pytest.mark.django_db
def test_submitter_can_answer_only_once_per_revision(otp_client, submitter, regulator_user, submitted_case):
    review(otp_client(regulator_user), submitted_case, "REVISION_REQUIRED", "Please add the dates.")
    client = otp_client(submitter)
    reply(client, submitted_case, "First answer")

    assert reply(client, submitted_case, "Second answer").status_code == 404


@pytest.mark.django_db
def test_closed_case_accepts_no_more_exchanges(otp_client, submitter, regulator_user, submitted_case):
    regulator_client = otp_client(regulator_user)
    review(regulator_client, submitted_case, "CLOSED", "Handled.")

    assert review(regulator_client, submitted_case, "REVISION_REQUIRED", "One more thing").status_code == 404
    assert reply(otp_client(submitter), submitted_case, "Hello").status_code == 404
    submitted_case.refresh_from_db()
    assert submitted_case.status == "CLOSED"


@pytest.mark.django_db
def test_history_lists_every_iteration(otp_client, submitter, regulator_user, submitted_case):
    review(otp_client(regulator_user), submitted_case, "REVISION_REQUIRED", "Please add the dates.")
    reply(otp_client(submitter), submitted_case, "It happened on 1 October.")
    review(otp_client(regulator_user), submitted_case, "CLOSED", "Handled.")

    iterations = submitted_case.iterations()

    assert [(i.submission.text, i.feedback.status) for i in iterations] == [
        ("", "REVISION_REQUIRED"),
        ("It happened on 1 October.", "CLOSED"),
    ]
    page = otp_client(submitter).get(reverse("case_detail", args=[submitted_case.reference])).content.decode()
    assert "Iteration 2" in page


@pytest.mark.django_db
def test_regulator_cannot_submit_cases(otp_client, regulator_user, case_form, submission_data):
    response = otp_client(regulator_user).post(reverse("create_case", args=[case_form.pk]), submission_data)

    assert response.status_code == 404
    assert not Case.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(("enabled", "hidden_path"), [(["incidents"], "/cases/"), (["cases"], "/incidents/")])
def test_disabled_base_module_answers_404(settings, otp_client, submitter, enabled, hidden_path):
    settings.BASE_MODULES = enabled

    assert otp_client(submitter).get(hidden_path).status_code == 404


@pytest.mark.django_db
def test_regulator_admin_only_lists_own_forms(otp_client, make_user, regulators, case_form):
    client = otp_client(make_user("regadmin@other.example.org", "RegulatorAdmin", regulator=regulators[1], is_admin=True))

    response = client.get(reverse("admin:cases_caseform_changelist"))

    assert response.status_code == 200
    assert "Test form" not in response.content.decode()
