from django.urls import path

from .views import case_detail, choose_case_form, create_case, download_attachment, get_cases

urlpatterns = [
    path("", get_cases, name="cases"),
    path("new", choose_case_form, name="choose_case_form"),
    path("new/<int:form_id>", create_case, name="create_case"),
    path("<str:reference>", case_detail, name="case_detail"),
    path("<str:reference>/attachment/<uuid:message_uuid>", download_attachment, name="case_attachment"),
]
