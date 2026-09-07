from django import template

register = template.Library()


@register.filter
def fc_status_for_context(recipe, context):
    """Django templates can't call a method with an argument directly —
    `recipe.fc_status_for_context(context)` needs this filter as the bridge."""
    return recipe.fc_status_for_context(context)
