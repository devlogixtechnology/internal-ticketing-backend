from django.urls import path
from .views import SignupView, CustomLoginView
from .views import custom_logout_view

app_name = 'accounts'

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', CustomLoginView.as_view(), name='login'),
   
    path('logout/', custom_logout_view, name='logout'),
]