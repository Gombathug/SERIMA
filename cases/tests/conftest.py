import pytest
from django.contrib.auth.models import Group
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from django.utils.translation import activate

from cases.models import CaseForm, CaseFormQuestion, CaseMessage, CaseQuestion, CaseQuestionChoice
from governanceplatform.models import Regulation, Regulator, RegulatorUser, User
from governanceplatform.permissions import update_all_group_permissions


@pytest.fixture(autouse=True)
def enabled_modules(settings):
    settings.BASE_MODULES = ["incidents", "cases"]


@pytest.fixture(autouse=True)
def case_files(tmp_path, monkeypatch):
    # The storage is resolved once at model load, so the test files are redirected here.
    monkeypatch.setattr(CaseMessage._meta.get_field("attachment"), "storage", FileSystemStorage(location=tmp_path))
    return tmp_path


@pytest.fixture
def make_user(db):
    update_all_group_permissions()

    def _make_user(email: str, group: str, regulator: Regulator | None = None, is_admin: bool = False) -> User:
        user = User.objects.create_user(
            email=email,
            password="unused-password",
            first_name=email.split("@")[0],
            accepted_terms=True,
            accepted_terms_date=timezone.now(),
            is_staff=group in ("RegulatorAdmin", "RegulatorUser"),
        )
        user.groups.add(Group.objects.get(name=group))
        if regulator:
            RegulatorUser.objects.create(user=user, regulator=regulator, is_regulator_administrator=is_admin)
        return user

    return _make_user


def make_regulator(name: str) -> Regulator:
    regulator = Regulator(country="BE", address="1 Street", email_for_notification=f"{name.lower()}@example.org")
    regulator.set_current_language("en")
    regulator.name = name
    regulator.save()
    return regulator


@pytest.fixture
def regulators(db):
    return make_regulator("IBPT"), make_regulator("Other")


@pytest.fixture
def case_form(regulators):
    activate("en")
    regulator = regulators[0]
    regulation = Regulation()
    regulation.set_current_language("en")
    regulation.label = "AI Act - Demo"
    regulation.save()
    regulation.regulators.add(regulator)

    request_type = CaseQuestion(question_type="SO", creator=regulator)
    request_type.set_current_language("en")
    request_type.label = "Type of request"
    request_type.save()
    for position, label in enumerate(["Question", "Complaint"]):
        choice = CaseQuestionChoice(question=request_type, position=position)
        choice.set_current_language("en")
        choice.label = label
        choice.save()

    description = CaseQuestion(question_type="FREETEXT", creator=regulator)
    description.set_current_language("en")
    description.label = "Description"
    description.save()

    form = CaseForm(regulation=regulation, creator=regulator)
    form.set_current_language("en")
    form.name = "Test form"
    form.save()
    CaseFormQuestion.objects.create(form=form, question=request_type, position=1, is_mandatory=True)
    CaseFormQuestion.objects.create(form=form, question=description, position=2, is_mandatory=True)
    return form


@pytest.fixture
def submission_data(case_form):
    """POST data that answers every question of the test form."""
    request_type, description = case_form.form_questions.all()
    complaint = request_type.question.choices.get(translations__label="Complaint")
    return {f"question_{request_type.pk}": str(complaint.pk), f"question_{description.pk}": "My complaint"}
