from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def split(value, delimiter):
    return value.split(delimiter)

@register.filter
def enumerate(value):
    """Zwraca (index, item) dla każdego elementu listy."""
    return list(__builtins__['enumerate'](value)) if isinstance(__builtins__, dict) else list(builtins_enumerate(value))

# Bezpieczniejsza wersja
import builtins as _builtins

@register.filter(name='enumerate')
def enumerate_filter(value):
    return list(_builtins.enumerate(value))
