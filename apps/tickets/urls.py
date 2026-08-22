from django.urls import path
from .views import dashboard

app_name = 'tickets'

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),
]