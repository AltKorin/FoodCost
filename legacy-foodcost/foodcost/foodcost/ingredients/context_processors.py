from .models import Supplier


def sidebar_suppliers(request):
    """Dostarcza listę dostawców do każdego szablonu (sidebar)."""
    if not request.user.is_authenticated:
        return {}
    return {
        'suppliers': Supplier.objects.filter(is_active=True).only('pk', 'name'),
    }
