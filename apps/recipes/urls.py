from django.urls import path
from . import views

app_name = 'recipes'

urlpatterns = [
    path('', views.RecipeListView.as_view(), name='recipe-list'),
    path('new/', views.recipe_create, name='recipe-create'),
    path('<int:pk>/', views.recipe_detail, name='recipe-detail'),
    path('<int:pk>/edit/', views.recipe_update, name='recipe-update'),
    path('<int:pk>/delete/', views.RecipeDeleteView.as_view(), name='recipe-delete'),

    path('contexts/', views.RecipeContextListView.as_view(), name='context-list'),
    path('contexts/new/', views.context_create, name='context-create'),
    path('contexts/<int:pk>/edit/', views.context_update, name='context-update'),
    path('contexts/<int:pk>/delete/', views.RecipeContextDeleteView.as_view(), name='context-delete'),

    path('menu/', views.MenuListView.as_view(), name='menu-list'),
    path('menu/new/', views.menu_create, name='menu-create'),
    path('menu/<int:pk>/', views.menu_detail, name='menu-detail'),
    path('menu/<int:pk>/edit/', views.menu_update, name='menu-update'),
    path('menu/<int:pk>/delete/', views.MenuDeleteView.as_view(), name='menu-delete'),
]
