from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('demo/', views.demo_start, name='demo'),
    path('demo/koniec/', views.demo_end, name='demo-end'),
    path('regulamin/', TemplateView.as_view(template_name='core/regulamin.html'), name='regulamin'),
]
