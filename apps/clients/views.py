"""
views.py — apps.clients
========================
Frontend dashboard views for managing Clients, Contacts,
Whitelisted Domains, and Whitelisted IPs.

All views are restricted to ADMIN role or Django superusers.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from .models import Client, WhitelistedDomain, WhitelistedIP, WhitelistedEmergencyEmail

from .forms import (
    ClientContactForm,
    ClientForm,
    WhitelistedDomainForm,
    WhitelistedIPForm,
)
from .models import Client, ClientContact, WhitelistedDomain, WhitelistedIP


from rest_framework import generics, permissions
from .models import WhitelistedEmergencyEmail
from .serializers import WhitelistedEmergencyEmailSerializer

class WhitelistedEmergencyEmailListCreateView(generics.ListCreateAPIView):
    queryset = WhitelistedEmergencyEmail.objects.all()
    serializer_class = WhitelistedEmergencyEmailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(added_by=self.request.user)

def _require_admin(user):
    """Return True if the user is an ADMIN or superuser."""
    return getattr(user, "role", None) == "ADMIN" or user.is_superuser


def _forbidden():
    return HttpResponseForbidden(
        "<h2>403 — Access Denied</h2>"
        "<p>This section is restricted to System Administrators.</p>"
    )


@login_required
def client_list(request):
    if not _require_admin(request.user):
        return _forbidden()

    clients = (
        Client.objects
        .prefetch_related("contacts", "whitelisted_domains", "whitelisted_ips", "whitelisted_emergency_emails")
        .order_by("name")
    )

    whitelisted_emails = WhitelistedEmergencyEmail.objects.select_related("client", "added_by").all()

    context = {
        "clients": clients,
        "total_clients": clients.count(),
        "active_clients": clients.filter(is_active=True).count(),
        "total_domains": WhitelistedDomain.objects.count(),
        "total_ips": WhitelistedIP.objects.count(),
        "whitelisted_emails": whitelisted_emails,
        "page_title": "Tenant & Whitelist Management",
    }
    return render(request, "clients/client_list.html", context)


# ---------------------------------------------------------------------------
# Client Create  /dashboard/clients/add/
# ---------------------------------------------------------------------------

@login_required
def client_create(request):
    if not _require_admin(request.user):
        return _forbidden()

    form = ClientForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            client = form.save()
            messages.success(request, f"✅ Client \"{client.name}\" created successfully.")
            return redirect("clients:detail", pk=client.pk)
        else:
            messages.error(request, "⚠️ Please fix the errors below before saving.")

    context = {
        "form":       form,
        "form_title": "Add New Client",
        "submit_label": "Create Client",
        "cancel_url": "clients:list",
    }
    return render(request, "clients/client_form.html", context)


# ---------------------------------------------------------------------------
# Client Detail  /dashboard/clients/<pk>/
# ---------------------------------------------------------------------------

@login_required
def client_detail(request, pk):
    if not _require_admin(request.user):
        return _forbidden()

    client = get_object_or_404(
        Client.objects.prefetch_related("contacts", "whitelisted_domains", "whitelisted_ips", "access_logs"),
        pk=pk,
    )

    context = {
        "client":        client,
        "contacts":      client.contacts.all(),
        "domains":       client.whitelisted_domains.all(),
        "ips":           client.whitelisted_ips.all(),
        "access_logs":   client.access_logs.all()[:25],
        "contact_form":  ClientContactForm(),
        "domain_form":   WhitelistedDomainForm(),
        "ip_form":       WhitelistedIPForm(),
    }
    return render(request, "clients/client_detail.html", context)


# ---------------------------------------------------------------------------
# Client Edit  /dashboard/clients/<pk>/edit/
# ---------------------------------------------------------------------------

@login_required
def client_edit(request, pk):
    if not _require_admin(request.user):
        return _forbidden()

    client = get_object_or_404(Client, pk=pk)
    form = ClientForm(request.POST or None, instance=client)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Client \"{client.name}\" updated successfully.")
            return redirect("clients:detail", pk=client.pk)
        else:
            messages.error(request, "⚠️ Please fix the errors below before saving.")

    context = {
        "form":         form,
        "form_title":   f"Edit Client — {client.name}",
        "submit_label": "Save Changes",
        "cancel_url":   None,
        "client":       client,
    }
    return render(request, "clients/client_form.html", context)


# ---------------------------------------------------------------------------
# Client Delete  POST /dashboard/clients/<pk>/delete/
# ---------------------------------------------------------------------------

@login_required
def client_delete(request, pk):
    if not _require_admin(request.user):
        return _forbidden()

    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        name = client.name
        client.delete()
        messages.success(request, f"🗑️ Client \"{name}\" and all related data deleted.")
    return redirect("clients:list")


# ---------------------------------------------------------------------------
# Contact Add  /dashboard/clients/<pk>/contacts/add/
# ---------------------------------------------------------------------------

@login_required
def contact_add(request, pk):
    if not _require_admin(request.user):
        return _forbidden()

    client = get_object_or_404(Client, pk=pk)

    if request.method == "POST":
        form = ClientContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.client = client
            contact.save()
            messages.success(request, f"✅ Contact \"{contact.name}\" added to {client.name}.")
            return redirect("clients:detail", pk=pk)
        else:
            # Re-render detail page with the erroneous contact form
            context = {
                "client":       client,
                "contacts":     client.contacts.all(),
                "domains":      client.whitelisted_domains.all(),
                "ips":          client.whitelisted_ips.all(),
                "contact_form": form,             # ← carries errors
                "domain_form":  WhitelistedDomainForm(),
                "ip_form":      WhitelistedIPForm(),
                "open_section": "contacts",       # auto-expand the contacts panel
            }
            return render(request, "clients/client_detail.html", context)

    return redirect("clients:detail", pk=pk)


# ---------------------------------------------------------------------------
# Contact Delete  POST /dashboard/clients/<pk>/contacts/<cpk>/delete/
# ---------------------------------------------------------------------------

@login_required
def contact_delete(request, pk, cpk):
    if not _require_admin(request.user):
        return _forbidden()

    contact = get_object_or_404(ClientContact, pk=cpk, client__pk=pk)
    if request.method == "POST":
        contact.delete()
        messages.success(request, "🗑️ Contact removed.")
    return redirect("clients:detail", pk=pk)


# ---------------------------------------------------------------------------
# Domain Add  /dashboard/clients/<pk>/domains/add/
# ---------------------------------------------------------------------------

@login_required
def domain_add(request, pk):
    if not _require_admin(request.user):
        return _forbidden()

    client = get_object_or_404(Client, pk=pk)

    if request.method == "POST":
        form = WhitelistedDomainForm(request.POST)
        if form.is_valid():
            domain = form.save(commit=False)
            domain.client = client
            domain.save()
            messages.success(request, f"✅ Domain \"{domain.domain_name}\" whitelisted.")
            return redirect("clients:detail", pk=pk)
        else:
            context = {
                "client":       client,
                "contacts":     client.contacts.all(),
                "domains":      client.whitelisted_domains.all(),
                "ips":          client.whitelisted_ips.all(),
                "contact_form": ClientContactForm(),
                "domain_form":  form,             # ← carries errors
                "ip_form":      WhitelistedIPForm(),
                "open_section": "domains",
            }
            return render(request, "clients/client_detail.html", context)

    return redirect("clients:detail", pk=pk)


# ---------------------------------------------------------------------------
# Domain Toggle  POST /dashboard/clients/<pk>/domains/<dpk>/toggle/
# ---------------------------------------------------------------------------

@login_required
def domain_toggle(request, pk, dpk):
    if not _require_admin(request.user):
        return _forbidden()

    domain = get_object_or_404(WhitelistedDomain, pk=dpk, client__pk=pk)
    if request.method == "POST":
        domain.is_active = not domain.is_active
        domain.save(update_fields=["is_active"])
        status_word = "activated" if domain.is_active else "deactivated"
        messages.success(request, f"Domain \"{domain.domain_name}\" {status_word}.")
    return redirect("clients:detail", pk=pk)


# ---------------------------------------------------------------------------
# Domain Delete  POST /dashboard/clients/<pk>/domains/<dpk>/delete/
# ---------------------------------------------------------------------------

@login_required
def domain_delete(request, pk, dpk):
    if not _require_admin(request.user):
        return _forbidden()

    domain = get_object_or_404(WhitelistedDomain, pk=dpk, client__pk=pk)
    if request.method == "POST":
        domain.delete()
        messages.success(request, "🗑️ Domain removed from whitelist.")
    return redirect("clients:detail", pk=pk)


# ---------------------------------------------------------------------------
# IP Add  /dashboard/clients/<pk>/ips/add/
# ---------------------------------------------------------------------------

@login_required
def ip_add(request, pk):
    if not _require_admin(request.user):
        return _forbidden()

    client = get_object_or_404(Client, pk=pk)

    if request.method == "POST":
        form = WhitelistedIPForm(request.POST)
        if form.is_valid():
            ip_entry = form.save(commit=False)
            ip_entry.client = client
            ip_entry.save()
            messages.success(request, f"✅ IP/CIDR \"{ip_entry.ip_or_cidr}\" whitelisted.")
            return redirect("clients:detail", pk=pk)
        else:
            context = {
                "client":       client,
                "contacts":     client.contacts.all(),
                "domains":      client.whitelisted_domains.all(),
                "ips":          client.whitelisted_ips.all(),
                "contact_form": ClientContactForm(),
                "domain_form":  WhitelistedDomainForm(),
                "ip_form":      form,             # ← carries errors
                "open_section": "ips",
            }
            return render(request, "clients/client_detail.html", context)

    return redirect("clients:detail", pk=pk)


# ---------------------------------------------------------------------------
# IP Delete  POST /dashboard/clients/<pk>/ips/<ipk>/delete/
# ---------------------------------------------------------------------------

@login_required
def ip_delete(request, pk, ipk):
    if not _require_admin(request.user):
        return _forbidden()

    ip_entry = get_object_or_404(WhitelistedIP, pk=ipk, client__pk=pk)
    if request.method == "POST":
        ip_entry.delete()
        messages.success(request, "🗑️ IP/CIDR removed from whitelist.")
    return redirect("clients:detail", pk=pk)
