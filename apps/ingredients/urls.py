from django.urls import path
from . import views, invoice_views, export_views

app_name = 'ingredients'

urlpatterns = [
    # Faktury (OCR: próba lub Pro)
    path('invoice/upload/', invoice_views.invoice_upload, name='invoice-upload'),
    path('invoice/estimate/', invoice_views.invoice_estimate, name='invoice-estimate'),
    path('invoice/request-access/', invoice_views.invoice_request_access, name='invoice-request-access'),
    path('invoice/confirm/', invoice_views.invoice_confirm, name='invoice-confirm'),

    # Eksport
    path('export/csv/', export_views.export_ingredients_csv, name='export-csv'),
    path('export/excel/', export_views.export_ingredients_excel, name='export-excel'),

    # Składniki
    path('', views.IngredientListView.as_view(), name='ingredient-list'),
    path('new/', views.IngredientCreateView.as_view(), name='ingredient-create'),
    path('<int:pk>/', views.ingredient_detail, name='ingredient-detail'),
    path('<int:pk>/edit/', views.IngredientUpdateView.as_view(), name='ingredient-update'),
    path('<int:pk>/delete/', views.IngredientDeleteView.as_view(), name='ingredient-delete'),

    # Kategorie
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/new/', views.CategoryCreateView.as_view(), name='category-create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category-delete'),

    # Dostawcy
    path('suppliers/', views.SupplierListView.as_view(), name='supplier-list'),
    path('suppliers/new/', views.SupplierCreateView.as_view(), name='supplier-create'),
    path('suppliers/<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier-update'),
    path('suppliers/<int:pk>/delete/', views.SupplierDeleteView.as_view(), name='supplier-delete'),

    # API
    path('api/<int:pk>/price/', views.api_ingredient_price, name='api-price'),
]
