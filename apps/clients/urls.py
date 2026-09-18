from django.urls import path
from apps.clients.views_api import ClientOnboardAPIView
from . import views
app_name = "clients"


urlpatterns = [
    path("",                     views.client_list,   name="list"),
    path("add/",                 views.client_create, name="create"),
    path("<int:pk>/",            views.client_detail, name="detail"),
    path("<int:pk>/edit/",       views.client_edit,   name="edit"),
    path("<int:pk>/delete/",     views.client_delete, name="delete"),
    path("<int:pk>/contacts/add/",                        views.contact_add,    name="contact_add"),
    path("<int:pk>/contacts/<int:cpk>/delete/",           views.contact_delete, name="contact_delete"),
    path("<int:pk>/domains/add/",                         views.domain_add,    name="domain_add"),
    path("<int:pk>/domains/<int:dpk>/toggle/",            views.domain_toggle, name="domain_toggle"),
    path("<int:pk>/domains/<int:dpk>/delete/",            views.domain_delete, name="domain_delete"),
    path("<int:pk>/ips/add/",                             views.ip_add,    name="ip_add"),
    path("<int:pk>/ips/<int:ipk>/delete/",                views.ip_delete, name="ip_delete"),
    path('api/admin/onboard/', ClientOnboardAPIView.as_view(), name='client-onboard-api'),
    path('api/admin/onboard/', ClientOnboardAPIView.as_view(), name='client-onboard'),
]
