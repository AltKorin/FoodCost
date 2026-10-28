from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('regulamin/', TemplateView.as_view(template_name='core/regulamin.html'), name='regulamin'),
]
