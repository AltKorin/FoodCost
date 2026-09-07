from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('setup/', views.setup, name='setup'),
    path('password/', views.password_change, name='password-change'),
    path('team/', views.team_list, name='team-list'),
    path('team/add/', views.team_add, name='team-add'),
    path('team/<int:pk>/remove/', views.team_remove, name='team-remove'),
]
