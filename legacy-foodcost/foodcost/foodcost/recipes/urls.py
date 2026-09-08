from django.urls import path
from . import views

urlpatterns = [
    path('', views.RecipeListView.as_view(), name='recipe_list'),
    path('<int:pk>/', views.recipe_detail, name='recipe_detail'),
    path('nowy/', views.recipe_edit, name='recipe_create'),
    path('<int:pk>/edytuj/', views.recipe_edit, name='recipe_edit'),
    path('raport/skladniki/', views.ingredient_report, name='ingredient_report'),
    path('api/cena/<int:ingredient_id>/', views.api_ingredient_price, name='api_ingredient_price'),
    path('api/v1/recipes/', views.api_recipes, name='api_recipes'),
]
