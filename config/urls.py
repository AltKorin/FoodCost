from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls', namespace='accounts')),
    path('', include('apps.core.urls', namespace='core')),
    path('ingredients/', include('apps.ingredients.urls', namespace='ingredients')),
    path('offers/', include('apps.offers.urls', namespace='offers')),  # feature flag OFFERS_ENABLED in apps.offers.urls
    path('recipes/', include('apps.recipes.urls', namespace='recipes')),
]

