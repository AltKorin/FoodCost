from django.urls import path
from . import views
from .invoice_views import invoice_upload, invoice_confirm
from .spreadsheet_views import spreadsheet_upload, spreadsheet_map, spreadsheet_confirm

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Składniki
    path('skladniki/', views.IngredientListView.as_view(), name='ingredient_list'),
    path('skladniki/nowy/', views.ingredient_edit, name='ingredient_create'),
    path('skladniki/<int:pk>/edytuj/', views.ingredient_edit, name='ingredient_edit'),
    path('skladniki/<int:pk>/usun/', views.ingredient_delete, name='ingredient_delete'),

    # Dostawcy
    path('dostawcy/', views.SupplierListView.as_view(), name='supplier_list'),
    path('dostawcy/nowy/', views.supplier_edit, name='supplier_create'),
    path('dostawcy/<int:pk>/edytuj/', views.supplier_edit, name='supplier_edit'),
    path('dostawcy/<int:pk>/usun/', views.supplier_delete, name='supplier_delete'),

    # Ceny
    path('ceny/<int:supplier_id>/', views.price_update, name='price_update'),

    # Import faktur PDF
    path('faktury/wgraj/', invoice_upload, name='invoice_upload'),
    path('faktury/potwierdz/', invoice_confirm, name='invoice_confirm'),

    # Import cenników Excel/CSV
    path('cennik/wgraj/', spreadsheet_upload, name='spreadsheet_upload'),
    path('cennik/kolumny/', spreadsheet_map, name='spreadsheet_map'),
    path('cennik/potwierdz/', spreadsheet_confirm, name='spreadsheet_confirm'),
]
