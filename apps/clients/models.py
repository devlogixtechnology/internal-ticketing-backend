
import ipaddress

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.conf import settings

def validate_ip_or_cidr(value: str) -> None:
    """
    Accept a plain IP address (v4 or v6) OR a CIDR network notation.

    Valid examples
    --------------
      192.168.1.1        — plain IPv4 address
      10.0.0.0/24        — IPv4 CIDR range
      2001:db8::1        — plain IPv6 address
      2001:db8::/32      — IPv6 CIDR range

    ``strict=False`` allows host bits to be set (e.g. 192.168.1.5/24).
    """
    try:
        ipaddress.ip_network(value.strip(), strict=False)
    except ValueError:
        raise ValidationError(
            '"%(value)s" is not a valid IP address or CIDR range '
            "(e.g. 192.168.1.1 or 10.0.0.0/24).",
            params={"value": value},
        )
class Client(models.Model):
    """Top-level tenant / client company."""

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Full legal or display name of the client.",
    )
    code = models.SlugField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Short, URL-safe identifier. Auto-generated from name if left blank.",
    )
    is_active = models.BooleanField(default=True)
    enforce_whitelisting = models.BooleanField(
        default=True,
        help_text="If True, strictly block non-whitelisted access. If False (Grace Mode), log the attempt but allow access.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Client"
        verbose_name_plural = "Clients"

   
    def save(self, *args, **kwargs):
        """Auto-generate a slug-style code from the name when not supplied."""
        if not self.code:
            self.code = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

class ClientContact(models.Model):
    """A point-of-contact person belonging to a Client."""

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    designation = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Client Contact"
        verbose_name_plural = "Client Contacts"

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"


class WhitelistedDomain(models.Model):

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="whitelisted_domains",
    )
    domain_name = models.CharField(
        max_length=253,
        help_text="Bare domain without scheme, e.g. acme.com",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["domain_name"]
        verbose_name = "Whitelisted Domain"
        verbose_name_plural = "Whitelisted Domains"
        unique_together = [("client", "domain_name")]

    def __str__(self) -> str:
        status = "✓" if self.is_active else "✗"
        return f"{status} {self.domain_name} — {self.client.code}"


# ---------------------------------------------------------------------------
# WhitelistedIP
# ---------------------------------------------------------------------------

class WhitelistedIP(models.Model):
    """
    An approved IPv4/IPv6 address or CIDR range for a Client.

    ``ip_or_cidr`` accepts
    ----------------------
      192.168.1.1    — plain address
      10.0.0.0/24   — network range
      2001:db8::/32 — IPv6 range
    """

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="whitelisted_ips",
    )
    ip_or_cidr = models.CharField(
        max_length=50,
        validators=[validate_ip_or_cidr],
        help_text="IPv4/IPv6 address or CIDR range, e.g. 10.0.0.0/24.",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional label for this entry, e.g. 'Head-office network'.",
    )

    class Meta:
        ordering = ["ip_or_cidr"]
        verbose_name = "Whitelisted IP / CIDR"
        verbose_name_plural = "Whitelisted IPs / CIDRs"
        unique_together = [("client", "ip_or_cidr")]

    def __str__(self) -> str:
        label = f" — {self.description}" if self.description else ""
        return f"{self.ip_or_cidr}{label} ({self.client.code})"


# ---------------------------------------------------------------------------
# AccessAttemptLog (BE5: Audit Logging & Grace Mode)
# ---------------------------------------------------------------------------

class AccessAttemptLog(models.Model):
    """
    Audit log for tenant access attempts, tracking allowed and blocked requests.
    """

    STATUS_CHOICES = [
        ("PASSED", "Passed"),
        ("BLOCKED", "Blocked"),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="access_logs",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    domain = models.CharField(max_length=255, null=True, blank=True)
    path = models.CharField(max_length=255, default="/")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Access Attempt Log"
        verbose_name_plural = "Access Attempt Logs"

    def __str__(self) -> str:
        client_code = self.client.code if self.client else "Unknown"
        return f"[{self.status}] {self.ip_address or self.domain} -> {self.path} ({client_code})"



class WhitelistedEmergencyEmail(models.Model):
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name="whitelisted_emergency_emails",
    )
    email = models.EmailField(unique=True)
    verified = models.BooleanField(default=False)
    purpose = models.CharField(
        max_length=255,
        help_text='Purpose, e.g. "VPS Down / VPN Down"',
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_emergency_emails",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Whitelisted Emergency Email"
        verbose_name_plural = "Whitelisted Emergency Emails"

    def __str__(self) -> str:
        status = "✓" if self.verified else "✗"
        return f"{status} {self.email} ({self.purpose}) — {self.client.code}"