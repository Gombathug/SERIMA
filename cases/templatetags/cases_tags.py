from django import template

register = template.Library()


@register.filter
def get_item(mapping: dict, key: str):
    return mapping.get(key)
