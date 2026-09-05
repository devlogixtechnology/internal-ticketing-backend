from django.urls import path
from .views import (
    SignupView,
    CustomLoginView,
    custom_logout_view,
    MagicLinkRequestView,
    MagicLinkVerifyView,
    APIKeyManagementView,
)

app_name = 'accounts'

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', custom_logout_view, name='logout'),
    path('auth/magic-link/', MagicLinkRequestView.as_view(), name='magic_link_request'),
    path('auth/magic-link/verify/<str:token>/', MagicLinkVerifyView.as_view(), name='magic_link_verify'),
    path('api-keys/', APIKeyManagementView.as_view(), name='api_keys'),
    path('api-keys/manage/', APIKeyManagementView.as_view(), name='api_keys_manage'),
]