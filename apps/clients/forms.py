"""
forms.py — apps.clients
=======================
ModelForms for the tenant / whitelist management dashboard.
"""

from django import forms

from .models import Client, ClientContact, WhitelistedDomain, WhitelistedIP


# ---------------------------------------------------------------------------
# Shared widget helpers
# ---------------------------------------------------------------------------

_INPUT  = {"class": "form-control"}
_SELECT = {"class": "form-select"}
_CHECK  = {"class": "form-check-input"}


# ---------------------------------------------------------------------------
# ClientForm
# ---------------------------------------------------------------------------

class ClientForm(forms.ModelForm):
    """Add / Edit a top-level Client tenant."""

    class Meta:
        model  = Client
        fields = ["name", "code", "is_active"]
        widgets = {
            "name":      forms.TextInput(attrs={**_INPUT,  "placeholder": "e.g. Acme Corporation"}),
            "code":      forms.TextInput(attrs={**_INPUT,  "placeholder": "Auto-generated if left blank"}),
            "is_active": forms.CheckboxInput(attrs=_CHECK),
        }
        help_texts = {
            "code": "URL-safe slug (auto-generated from name when left blank).",
        }


# ---------------------------------------------------------------------------
# ClientContactForm
# ---------------------------------------------------------------------------

class ClientContactForm(forms.ModelForm):
    """Add a contact person to a Client."""

    class Meta:
        model  = ClientContact
        fields = ["name", "email", "phone", "designation"]
        widgets = {
            "name":        forms.TextInput(attrs={**_INPUT, "placeholder": "Full name"}),
            "email":       forms.EmailInput(attrs={**_INPUT, "placeholder": "email@example.com"}),
            "phone":       forms.TextInput(attrs={**_INPUT, "placeholder": "+92 300 0000000"}),
            "designation": forms.TextInput(attrs={**_INPUT, "placeholder": "e.g. IT Manager"}),
        }


# ---------------------------------------------------------------------------
# WhitelistedDomainForm
# ---------------------------------------------------------------------------

class WhitelistedDomainForm(forms.ModelForm):
    """Add a whitelisted email / web domain to a Client."""

    class Meta:
        model  = WhitelistedDomain
        fields = ["domain_name", "is_active"]
        widgets = {
            "domain_name": forms.TextInput(attrs={**_INPUT, "placeholder": "e.g. acme.com"}),
            "is_active":   forms.CheckboxInput(attrs=_CHECK),
        }


# ---------------------------------------------------------------------------
# WhitelistedIPForm
# ---------------------------------------------------------------------------

class WhitelistedIPForm(forms.ModelForm):
    """
    Add a whitelisted IP address or CIDR range to a Client.

    Validation is handled by the model-level ``validate_ip_or_cidr`` validator,
    so malformed CIDR values (e.g. 999.999.0.0/24) will surface as clean
    form errors automatically.
    """

    class Meta:
        model  = WhitelistedIP
        fields = ["ip_or_cidr", "description"]
        widgets = {
            "ip_or_cidr":  forms.TextInput(attrs={**_INPUT, "placeholder": "e.g. 10.0.0.0/24 or 192.168.1.1"}),
            "description": forms.TextInput(attrs={**_INPUT, "placeholder": "Optional label, e.g. Head-office"}),
        }
