from django.urls import path
from .views import SignupView, CustomLoginView
from .views import custom_logout_view
from .views import APIKeyManagementView

app_name = 'accounts'
from .views import (
    MagicLinkRequestView,
    MagicLinkVerifyView,
    APIKeyManagementView,
)
urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', CustomLoginView.as_view(), name='login'),
   
    path('logout/', custom_logout_view, name='logout'),
    path('auth/magic-link/', MagicLinkRequestView.as_view(), name='magic_link_request'),
    path('auth/magic-link/verify/<str:token>/', MagicLinkVerifyView.as_view(), name='magic_link_verify'),
    
  path("api-keys/", APIKeyManagementView.as_view(), name="api_keys"),
]