import os
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields

from governanceplatform.helpers import build_crockford_token

from .globals import ATTACHMENT_EXTENSIONS, CASE_STATUS, QUESTION_TYPES, REFERENCE_PREFIX
from .validators import validate_attachment_size


def case_files_storage():
    # Same rule as PATH_FOR_REPORTING_PDF: never statically served, only through
    # the permission-checked download view. Callable so migrations keep no path.
    return FileSystemStorage(location=os.path.join(settings.PATH_FOR_REPORTING_PDF, "cases"))


class CreatorMixin(models.Model):
    """Owned by the regulator that created it, like the incident configuration models."""

    creator_name = models.CharField(verbose_name=_("Creator name"), max_length=255, blank=True, default=None, null=True)
    creator = models.ForeignKey(
        "governanceplatform.Regulator",
        verbose_name=_("Creator"),
        on_delete=models.SET_NULL,
        blank=True,
        default=None,
        null=True,
    )

    class Meta:
        abstract = True


class CaseQuestion(CreatorMixin, TranslatableModel):
    question_type = models.CharField(
        max_length=10,
        choices=QUESTION_TYPES,
        blank=False,
        default=QUESTION_TYPES[0][0],
        verbose_name=_("Type"),
    )
    translations = TranslatedFields(
        label=models.TextField(verbose_name=_("Label")),
        tooltip=models.TextField(verbose_name=_("Tooltip"), blank=True, default=""),
    )

    def is_in_use(self) -> bool:
        return self.caseanswer_set.exists()

    def __str__(self):
        return self.safe_translation_getter("label", any_language=True) or ""

    class Meta:
        verbose_name = _("Question")
        verbose_name_plural = _("Questions")


class CaseQuestionChoice(TranslatableModel):
    question = models.ForeignKey(CaseQuestion, on_delete=models.CASCADE, related_name="choices", verbose_name=_("Question"))
    position = models.IntegerField(verbose_name=_("Position"), default=0)
    translations = TranslatedFields(label=models.CharField(verbose_name=_("Answer"), max_length=255))

    def __str__(self):
        return self.safe_translation_getter("label", any_language=True) or ""

    class Meta:
        ordering = ["position", "id"]
        verbose_name = _("Predefined answer")
        verbose_name_plural = _("Predefined answers")


class CaseForm(CreatorMixin, TranslatableModel):
    """A form a person fills in to open a case. Its regulator receives the cases."""

    translations = TranslatedFields(
        name=models.CharField(verbose_name=_("Name"), max_length=255),
        description=models.TextField(verbose_name=_("Description"), blank=True, default=""),
    )
    regulation = models.ForeignKey(
        "governanceplatform.Regulation",
        verbose_name=_("Regulation"),
        on_delete=models.PROTECT,
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Only active forms can be used to submit a case."),
    )
    allow_attachment = models.BooleanField(default=True, verbose_name=_("Attachment allowed on submission"))
    questions = models.ManyToManyField(CaseQuestion, through="CaseFormQuestion", verbose_name=_("Questions"))

    def is_in_use(self) -> bool:
        return self.case_set.exists()

    def __str__(self):
        return self.safe_translation_getter("name", any_language=True) or ""

    class Meta:
        verbose_name = _("Form")
        verbose_name_plural = _("Forms")


class CaseFormQuestion(models.Model):
    form = models.ForeignKey(CaseForm, on_delete=models.CASCADE, related_name="form_questions")
    question = models.ForeignKey(CaseQuestion, on_delete=models.PROTECT, verbose_name=_("Question"))
    position = models.IntegerField(verbose_name=_("Position"), default=0)
    is_mandatory = models.BooleanField(default=False, verbose_name=_("Mandatory"))

    def __str__(self):
        return str(self.question)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = _("Question of the form")
        verbose_name_plural = _("Questions of the form")
        constraints = [models.UniqueConstraint(fields=["form", "question"], name="unique_question_per_case_form")]


class CaseQuerySet(models.QuerySet):
    def visible_to(self, user) -> CaseQuerySet:
        """Regulators see the cases sent to their regulator, everybody else only their own."""
        if user.is_regulator():
            return self.filter(regulator__in=user.regulators.all())
        if user.is_observer() or user.in_group("PlatformAdmin"):
            return self.none()
        return self.filter(submitter=user)


class Case(models.Model):
    reference = models.CharField(verbose_name=_("Reference"), max_length=32, unique=True, editable=False)
    form = models.ForeignKey(CaseForm, on_delete=models.PROTECT, verbose_name=_("Form"))
    regulator = models.ForeignKey("governanceplatform.Regulator", on_delete=models.PROTECT, verbose_name=_("Regulator"))
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Submitter"),
    )
    submitter_name = models.CharField(verbose_name=_("Submitter name"), max_length=255)
    submitter_email = models.EmailField(verbose_name=_("Submitter email"))
    company = models.ForeignKey(
        "governanceplatform.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Operator"),
    )
    status = models.CharField(verbose_name=_("Status"), max_length=20, choices=CASE_STATUS, default=CASE_STATUS[0][0])
    created_at = models.DateTimeField(verbose_name=_("Creation date"), default=timezone.now)
    updated_at = models.DateTimeField(verbose_name=_("Last update"), default=timezone.now)

    objects = CaseQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._new_reference()
        super().save(*args, **kwargs)

    @staticmethod
    def _new_reference() -> str:
        while True:
            reference = REFERENCE_PREFIX + build_crockford_token()
            if not Case.objects.filter(reference=reference).exists():
                return reference

    def iterations(self) -> list[CaseIteration]:
        """One iteration per submission or reply of the submitter, with the regulator's feedback on it."""
        iterations: list[CaseIteration] = []
        for message in self.messages.all():
            if message.is_from_regulator and iterations:
                iterations[-1].feedback = message
            else:
                iterations.append(CaseIteration(number=len(iterations) + 1, submission=message))
        return iterations

    def __str__(self):
        return self.reference

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = _("Case")
        verbose_name_plural = _("Cases")
        indexes = [
            models.Index(fields=["regulator", "status"]),
            models.Index(fields=["updated_at"]),
        ]


class CaseAnswer(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(CaseQuestion, on_delete=models.PROTECT, verbose_name=_("Question"))
    position = models.IntegerField(default=0)
    answer = models.TextField(verbose_name=_("Answer"), blank=True, default="")
    choices = models.ManyToManyField(CaseQuestionChoice, blank=True, verbose_name=_("Predefined answers"))

    class Meta:
        ordering = ["position", "id"]


class CaseMessage(models.Model):
    """A step of the review cycle: the submission, a reply of the submitter or a decision of the regulator."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    author_name = models.CharField(max_length=255)
    is_from_regulator = models.BooleanField(default=False)
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=20,
        choices=CASE_STATUS,
        help_text=_("Status of the case after this step"),
    )
    text = models.TextField(verbose_name=_("Comment"), blank=True, default="")
    attachment = models.FileField(
        verbose_name=_("Attachment"),
        storage=case_files_storage,
        upload_to="%Y/%m/",
        blank=True,
        validators=[FileExtensionValidator(ATTACHMENT_EXTENSIONS), validate_attachment_size],
    )
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def attachment_name(self) -> str:
        return os.path.basename(self.attachment.name) if self.attachment else ""

    class Meta:
        ordering = ["created_at", "id"]


@dataclass
class CaseIteration:
    number: int
    submission: CaseMessage
    feedback: CaseMessage | None = None
