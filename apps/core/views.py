from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from apps.accounts.decorators import setup_required


def dashboard(request):
    # `/` robi za router: gość dostaje darmowy kalkulator (lead gen), nie
    # ekran logowania — logujący/mający konto trafiają na właściwy dashboard.
    if not request.user.is_authenticated:
        return render(request, 'core/landing.html')
    if not request.user.organization_id:
        return redirect('accounts:setup')
    return _dashboard(request)


@login_required
@setup_required
def _dashboard(request):
    org = request.user.organization
    from apps.ingredients.models import Ingredient, Supplier
    from apps.recipes.models import Recipe

    recipes = Recipe.objects.filter(organization=org)
    danger_count = sum(1 for r in recipes if r.fc_status == 'danger')
    warning_count = sum(1 for r in recipes if r.fc_status == 'warning')

    context = {
        'recipe_count': recipes.count(),
        'ingredient_count': Ingredient.objects.filter(organization=org, is_active=True).count(),
        'supplier_count': Supplier.objects.filter(organization=org).count(),
        'danger_count': danger_count,
        'warning_count': warning_count,
        'recent_recipes': recipes.order_by('-updated_at')[:5],
    }
    return render(request, 'core/dashboard.html', context)
