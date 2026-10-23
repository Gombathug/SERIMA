"""Turn the loaded docs/screenshots/fixture.json into the local case management demo.

Run from the repository root, after `loaddata docs/screenshots/fixture.json`:

    python demo/setup_demo.py [--password <password>]

- gives the fixture's role accounts the demo email addresses and a known password,
- accepts the terms of use for them and removes any TOTP device,
- switches off the Security Objectives and Reporting modules (re-enable them in the
  admin: Functionalities > Roles),
- renames Regulator A to IBPT, adds the "AI Act - Demo" regulation and a test form
  with two questions for the case management module. No case is created.
"""

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "governanceplatform.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402
from django.utils.timezone import now  # noqa: E402
from django_otp.plugins.otp_totp.models import TOTPDevice  # noqa: E402

from cases.models import Case, CaseForm, CaseFormQuestion, CaseQuestion, CaseQuestionChoice  # noqa: E402
from governanceplatform.models import CompanyUser, Functionality, Regulation, RegulatorUser, User  # noqa: E402
from governanceplatform.permissions import set_platform_admin_permissions  # noqa: E402

DEFAULT_PASSWORD = "SerimaDemo2026!"
LANGUAGES = ("en", "fr")

# fixture email -> demo email
ACCOUNTS = {
    "platform-admin@example.org": "platformadmin@bipt.be",
    "regulator-admin@example.org": "RegAdmin@bipt.be",
    "regulator-user@example.org": "RegUser@bipt.be",
    "operator-admin@example.org": "OpAdmin@bipt.be",
    "operator-user@example.org": "OpUser@bipt.be",
    # the fixture's incident user: a person without an organisation, like a citizen filing a complaint
    "incident-user@example.org": "NewUser@bipt.be",
}

IBPT = {
    "name": "IBPT",
    "full_name": "L'Institut belge des services postaux et des télécommunications",
}
REGULATION_LABEL = "AI Act - Demo"


def translate(obj, **values_by_language) -> None:
    """values_by_language: field -> {language: value}, or field -> value for all languages."""
    for language in LANGUAGES:
        obj.set_current_language(language)
        for field, value in values_by_language.items():
            setattr(obj, field, value[language] if isinstance(value, dict) else value)
    obj.save()


def setup_accounts(password: str) -> None:
    for fixture_email, demo_email in ACCOUNTS.items():
        user = User.objects.filter(email__iexact=demo_email).first() or User.objects.get(email=fixture_email)
        user.email = demo_email
        user.set_password(password)
        user.accepted_terms = True
        user.accepted_terms_date = now()
        if demo_email == "NewUser@bipt.be":
            user.first_name, user.last_name = "New", "User"
            CompanyUser.objects.filter(user=user).delete()
        user.save()
        TOTPDevice.objects.filter(user=user).delete()
        if user.groups.filter(name="PlatformAdmin").exists():
            set_platform_admin_permissions(user)
        print(f"  {demo_email:<24} {', '.join(user.groups.values_list('name', flat=True))}")  # noqa: T201


def setup_case_management() -> None:
    regulator = RegulatorUser.objects.get(user__email__iexact="RegAdmin@bipt.be").regulator
    translate(regulator, **IBPT)
    regulator.email_for_notification = "notification@bipt.be"
    regulator.save()

    regulation = Regulation.objects.filter(translations__label=REGULATION_LABEL).first() or Regulation()
    translate(regulation, label=REGULATION_LABEL)
    regulation.regulators.add(regulator)

    Case.objects.all().delete()
    CaseForm.objects.all().delete()
    CaseQuestion.objects.all().delete()

    owned = {"creator": regulator, "creator_name": str(regulator)}
    request_type = CaseQuestion(question_type="SO", **owned)
    translate(request_type, label={"en": "Type of request", "fr": "Type de demande"}, tooltip="")
    for position, labels in enumerate(
        [{"en": "Question", "fr": "Question"}, {"en": "Complaint", "fr": "Plainte"}, {"en": "Information", "fr": "Information"}]
    ):
        translate(CaseQuestionChoice(question=request_type, position=position), label=labels)

    description = CaseQuestion(question_type="FREETEXT", **owned)
    translate(
        description,
        label={"en": "Description of your request", "fr": "Description de votre demande"},
        tooltip={
            "en": "Describe the facts, dates and the AI system concerned.",
            "fr": "Décrivez les faits, les dates et le système d'IA concerné.",
        },
    )

    form = CaseForm(regulation=regulation, **owned)
    translate(
        form,
        name={"en": "Test form", "fr": "Formulaire test"},
        description={"en": "Example form with two questions.", "fr": "Formulaire d'exemple avec deux questions."},
    )
    CaseFormQuestion.objects.create(form=form, question=request_type, position=1, is_mandatory=True)
    CaseFormQuestion.objects.create(form=form, question=description, position=2, is_mandatory=True)
    print(f"  {regulator} / {regulation}: form '{form}' with 2 questions, no case")  # noqa: T201


@transaction.atomic
def main(password: str) -> None:
    setup_accounts(password)

    for functionality in Functionality.objects.all():
        functionality.roles.clear()
    print("  Security Objectives and Reporting switched off (Functionality roles cleared)")  # noqa: T201

    setup_case_management()


if __name__ == "__main__":
    if not settings.DEBUG:
        sys.exit("refusing to run with DEBUG off: this script sets known passwords")
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    main(parser.parse_args().password)
