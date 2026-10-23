from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from governanceplatform.admin import CustomTranslatableAdmin, CustomTranslatableTabularInline, admin_site
from governanceplatform.helpers import generate_display_methods, set_creator
from governanceplatform.mixins import PermissionMixin
from governanceplatform.models import Regulation

from .models import CaseForm, CaseFormQuestion, CaseQuestion, CaseQuestionChoice


class OwnRegulatorMixin:
    """A regulator administrator works on the questions and forms of its own regulator only."""

    def get_queryset(self, request):
        return super().get_queryset(request).filter(creator__in=request.user.regulators.all())

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly_fields.append("creator")
        return readonly_fields

    def save_model(self, request, obj, form, change):
        set_creator(request, obj, change)
        super().save_model(request, obj, form, change)


class CaseQuestionChoiceInline(CustomTranslatableTabularInline):
    model = CaseQuestionChoice
    fields = ["label", "position"]
    verbose_name = _("Predefined answer")
    verbose_name_plural = _("Predefined answers (single and multiple choice only)")
    extra = 0


@admin.register(CaseQuestion, site=admin_site)
class CaseQuestionAdmin(OwnRegulatorMixin, PermissionMixin, CustomTranslatableAdmin):
    list_display = ["label_display", "question_type", "get_choices"]
    translated_fields = ["label"]
    search_fields = ["translations__label", "choices__translations__label"]
    list_filter = ["question_type"]
    fields = ["question_type", "label", "tooltip"]
    inlines = [CaseQuestionChoiceInline]

    @admin.display(description=_("Predefined answers"))
    def get_choices(self, obj):
        return ", ".join(str(choice) for choice in obj.choices.all())


class CaseFormQuestionInline(admin.TabularInline):
    model = CaseFormQuestion
    fields = ["position", "question", "is_mandatory"]
    verbose_name = _("Question")
    verbose_name_plural = _("Questions of the form")
    extra = 0

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "question":
            kwargs["queryset"] = CaseQuestion.objects.filter(creator__in=request.user.regulators.all())
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(CaseForm, site=admin_site)
class CaseFormAdmin(OwnRegulatorMixin, PermissionMixin, CustomTranslatableAdmin):
    list_display = ["name_display", "regulation", "is_active", "get_question_count"]
    translated_fields = ["name"]
    search_fields = ["translations__name", "translations__description"]
    list_filter = ["is_active"]
    fields = ["name", "description", "regulation", "is_active", "allow_attachment"]
    inlines = [CaseFormQuestionInline]
    # questions and order stay editable once cases exist: answers keep their own copy of the position
    change_ignores_in_use = True

    @admin.display(description=_("Questions"))
    def get_question_count(self, obj):
        return obj.form_questions.count()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "regulation":
            kwargs["queryset"] = Regulation.objects.filter(regulators__in=request.user.regulators.all()).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


for admin_class, translated_fields in ((CaseQuestionAdmin, ["label"]), (CaseFormAdmin, ["name"])):
    for name, method in generate_display_methods(translated_fields).items():
        setattr(admin_class, name, method)
