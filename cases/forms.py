from django import forms
from django.utils.translation import gettext_lazy as _

from .globals import ATTACHMENT_EXTENSIONS, REVIEW_DECISIONS
from .models import CaseForm, CaseMessage

ATTACHMENT_ACCEPT = ",".join(f".{extension}" for extension in ATTACHMENT_EXTENSIONS)


def attachment_field() -> forms.FileField:
    return forms.FileField(
        label=_("Attachment"),
        required=False,
        validators=CaseMessage._meta.get_field("attachment").validators,
        widget=forms.ClearableFileInput(attrs={"accept": ATTACHMENT_ACCEPT}),
        help_text=_("Optional. Allowed: %(extensions)s, 10 MB maximum.") % {"extensions": ", ".join(ATTACHMENT_EXTENSIONS)},
    )


class CaseSubmissionForm(forms.Form):
    """One field per question of the case form, in its order, plus the optional attachment."""

    def __init__(self, *args, case_form: CaseForm, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_questions = list(case_form.form_questions.select_related("question").prefetch_related("question__choices"))
        for form_question in self.form_questions:
            self.fields[self.field_name(form_question)] = self._build_field(form_question)
        if case_form.allow_attachment:
            self.fields["attachment"] = attachment_field()

    @staticmethod
    def field_name(form_question) -> str:
        return f"question_{form_question.pk}"

    @staticmethod
    def _build_field(form_question) -> forms.Field:
        question = form_question.question
        common = {
            "label": str(question),
            "required": form_question.is_mandatory,
            "help_text": question.safe_translation_getter("tooltip", any_language=True) or "",
        }
        choices = [(choice.pk, str(choice)) for choice in question.choices.all()]
        match question.question_type:
            case "SO":
                return forms.ChoiceField(choices=choices, widget=forms.RadioSelect, **common)
            case "MULTI":
                return forms.MultipleChoiceField(choices=choices, widget=forms.CheckboxSelectMultiple, **common)
            case "DATE":
                return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **common)
            case _:
                return forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), **common)


class CaseReviewForm(forms.Form):
    """The regulator's decision on a case under review."""

    decision = forms.ChoiceField(label=_("Decision"), choices=REVIEW_DECISIONS, widget=forms.RadioSelect)
    text = forms.CharField(
        label=_("Comment"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text=_("Required to request a revision: explain what the submitter must add or correct."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attachment"] = attachment_field()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("decision") == "REVISION_REQUIRED" and not cleaned_data.get("text"):
            self.add_error("text", _("A comment is required to request a revision."))
        return cleaned_data


class CaseReplyForm(forms.Form):
    """The submitter's answer to a revision request."""

    text = forms.CharField(label=_("Your answer"), widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attachment"] = attachment_field()
