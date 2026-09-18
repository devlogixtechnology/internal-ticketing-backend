"""
admin.py — apps.clients
========================
Django Admin configuration for tenant/whitelist models.
"""

from django.contrib import admin

from .models import (
    AccessAttemptLog,
    Client,
    ClientContact,
    WhitelistedDomain,
    WhitelistedIP,
)


# ---------------------------------------------------------------------------
# Inlines  (shown nested inside ClientAdmin)
# ---------------------------------------------------------------------------

class ClientContactInline(admin.TabularInline):
    model = ClientContact
    extra = 0
    fields = ("name", "email", "phone", "designation")
    show_change_link = True


class WhitelistedDomainInline(admin.TabularInline):
    model = WhitelistedDomain
    extra = 0
    fields = ("domain_name", "is_active")
    show_change_link = True


class WhitelistedIPInline(admin.TabularInline):
    model = WhitelistedIP
    extra = 0
    fields = ("ip_or_cidr", "description")
    show_change_link = True


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display  = ("name", "code", "is_active", "enforce_whitelisting", "contact_count", "created_at")
    list_filter   = ("is_active", "enforce_whitelisting")
    search_fields = ("name", "code")
    prepopulated_fields = {"code": ("name",)}
    readonly_fields = ("created_at",)
    ordering = ("name",)
    inlines = [ClientContactInline, WhitelistedDomainInline, WhitelistedIPInline]

    @admin.display(description="Contacts #")
    def contact_count(self, obj):
        return obj.contacts.count()


# ---------------------------------------------------------------------------
# ClientContact
# ---------------------------------------------------------------------------

@admin.register(ClientContact)
class ClientContactAdmin(admin.ModelAdmin):
    list_display  = ("name", "email", "phone", "designation", "client")
    list_filter   = ("client",)
    search_fields = ("name", "email", "phone", "designation", "client__name")
    autocomplete_fields = ("client",)
    ordering = ("name",)


# ---------------------------------------------------------------------------
# WhitelistedDomain
# ---------------------------------------------------------------------------

@admin.register(WhitelistedDomain)
class WhitelistedDomainAdmin(admin.ModelAdmin):
    list_display  = ("domain_name", "client", "is_active")
    list_filter   = ("is_active", "client")
    search_fields = ("domain_name", "client__name", "client__code")
    autocomplete_fields = ("client",)
    ordering = ("domain_name",)


# ---------------------------------------------------------------------------
# WhitelistedIP
# ---------------------------------------------------------------------------

@admin.register(WhitelistedIP)
class WhitelistedIPAdmin(admin.ModelAdmin):
    list_display  = ("ip_or_cidr", "client", "description")
    list_filter   = ("client",)
    search_fields = ("ip_or_cidr", "description", "client__name", "client__code")
    autocomplete_fields = ("client",)
    ordering = ("ip_or_cidr",)


# ---------------------------------------------------------------------------
# AccessAttemptLog (BE5: Audit Log Admin)
# ---------------------------------------------------------------------------

@admin.register(AccessAttemptLog)
class AccessAttemptLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "status", "client", "ip_address", "domain", "path")
    list_filter = ("status", "client", "created_at")
    search_fields = ("ip_address", "domain", "path", "client__name", "client__code")
    readonly_fields = ("client", "ip_address", "domain", "path", "status", "created_at")
    ordering = ("-created_at",)

