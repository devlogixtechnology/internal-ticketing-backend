from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'tickets'

# DRF Router Configuration
router = DefaultRouter()
router.register(r'api/tickets-set', views.TicketViewSet, basename='ticket-set')

urlpatterns = [
    # Template Views
    path('dashboard/', views.dashboard, name='dashboard'),
    path('<int:ticket_id>/', views.ticket_detail, name='detail'),
   path('<int:ticket_id>/assign/', views.assign_support, name='assign_support'),
    path('server-health/', views.server_health_dashboard, name='server_health_dashboard'),

    # DRF API Endpoints
    path('api/tickets/', views.ticket_list_create_api, name='ticket_list_create_api'),
    path('api/tickets/create/', views.create_ticket_api, name='create'),
    path('api/tickets/<int:ticket_id>/assign/', views.assign_ticket_api, name='assign_ticket_api'),
    path('api/tickets/<int:ticket_id>/status/', views.change_status_api, name='change_status'),
    path('api/tickets/<int:ticket_id>/attachments/upload/', views.upload_attachment_api, name='upload_attachment'),
    path('api/categories/create/', views.create_category_api, name='create_category'),
    path('emergency-whitelists/', views.emergency_whitelists, name='emergency_whitelists'),
    path('ticket/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
  
    path('tickets/<int:ticket_id>/comment/', views.add_comment, name='add_comment'),
    path('active-tickets/', views.active_tickets, name='active_tickets'), # Naya route
    # Include DRF Router URLs
    path('', include(router.urls)),
]