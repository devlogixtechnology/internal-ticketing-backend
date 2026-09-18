from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('api/unread/', views.unread_notifications_api, name='unread_list'),
    path('api/<int:notification_id>/read/', views.mark_notification_read_api, name='mark_read'),
    path('api/mark-all-read/', views.mark_all_read_api, name='mark_all_read'),
]