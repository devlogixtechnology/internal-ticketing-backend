from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/tickets/create/', views.create_ticket_api, name='create'),
    path('api/tickets/<int:ticket_id>/assign/', views.assign_ticket_api, name='assign'),
    path('api/tickets/<int:ticket_id>/status/', views.change_status_api, name='change_status'),
    path('api/categories/create/', views.create_category_api, name='create_category'),
    path('tickets/<int:ticket_id>/assign/', views.assign_support, name='assign_support'),
]
