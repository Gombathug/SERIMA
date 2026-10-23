from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _

from .globals import ATTACHMENT_MAX_SIZE


def validate_attachment_size(file) -> None:
    if file.size > ATTACHMENT_MAX_SIZE:
        raise ValidationError(
            _("The file is too large (maximum %(size)s)."),
            params={"size": filesizeformat(ATTACHMENT_MAX_SIZE)},
        )
