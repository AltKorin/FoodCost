from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls', namespace='accounts')),
    path('', include('apps.core.urls', namespace='core')),
    path('ingredients/', include('apps.ingredients.urls', namespace='ingredients')),
    path('recipes/', include('apps.recipes.urls', namespace='recipes')),
]
