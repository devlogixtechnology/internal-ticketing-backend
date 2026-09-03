"""
serializers.py — apps.clients
==============================
DRF serializers for all four tenant/whitelist models.

Serializers
-----------
  ClientSerializer
  ClientContactSerializer
  WhitelistedDomainSerializer
  WhitelistedIPSerializer   ← includes CIDR normalisation
"""

import ipaddress

from rest_framework import serializers

from .models import Client, ClientContact, WhitelistedDomain, WhitelistedIP


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ClientSerializer(serializers.ModelSerializer):
    """Full CRUD serializer for the Client (tenant) model."""

    class Meta:
        model = Client
        fields = ["id", "name", "code", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            # Allow blank so the model's save() can auto-generate the slug.
            "code": {"required": False, "allow_blank": True},
        }


# ---------------------------------------------------------------------------
# ClientContact
# ---------------------------------------------------------------------------

class ClientContactSerializer(serializers.ModelSerializer):
    """Full CRUD serializer for ClientContact."""

    # Convenience read-only field — shows client display name alongside FK id.
    client_name = serializers.CharField(source="client.name", read_only=True)

    class Meta:
        model = ClientContact
        fields = ["id", "client", "client_name", "name", "email", "phone", "designation"]
        read_only_fields = ["id", "client_name"]


# ---------------------------------------------------------------------------
# WhitelistedDomain
# ---------------------------------------------------------------------------

class WhitelistedDomainSerializer(serializers.ModelSerializer):
    """Full CRUD serializer for WhitelistedDomain."""

    client_name = serializers.CharField(source="client.name", read_only=True)

    class Meta:
        model = WhitelistedDomain
        fields = ["id", "client", "client_name", "domain_name", "is_active"]
        read_only_fields = ["id", "client_name"]

    # ------------------------------------------------------------------
    def validate_domain_name(self, value: str) -> str:
        """
        Normalise and validate a domain name.

        Steps:
          1. Strip whitespace and a leading ``@`` (common copy-paste mistake).
          2. Lowercase the value for consistent storage.
          3. Reject values that contain ``://`` or ``/`` (no schemes or paths).
          4. Ensure at least one ``.`` is present.
        """
        value = value.strip().lstrip("@").lower()

        if "://" in value or "/" in value:
            raise serializers.ValidationError(
                "Enter a bare domain without scheme or path "
                "(e.g. acme.com, not https://acme.com)."
            )
        if "." not in value:
            raise serializers.ValidationError(
                "Enter a valid domain name with at least one dot (e.g. acme.com)."
            )
        return value


# ---------------------------------------------------------------------------
# WhitelistedIP
# ---------------------------------------------------------------------------

class WhitelistedIPSerializer(serializers.ModelSerializer):
    """
    Full CRUD serializer for WhitelistedIP.

    Validation is applied at two layers:
      • Model layer  — ``validate_ip_or_cidr`` validator on the field itself,
                       invoked automatically by DRF's ``run_validators``.
      • Serializer layer — ``validate_ip_or_cidr`` method below normalises
                           the canonical form (e.g. 10.0.0.5/24 → 10.0.0.0/24)
                           and surfaces a clean DRF-style error message.
    """

    client_name = serializers.CharField(source="client.name", read_only=True)

    class Meta:
        model = WhitelistedIP
        fields = ["id", "client", "client_name", "ip_or_cidr", "description"]
        read_only_fields = ["id", "client_name"]

    # ------------------------------------------------------------------
    def validate_ip_or_cidr(self, value: str) -> str:
        """
        Validate and normalise an IP address or CIDR range.

        ``strict=False`` allows host bits to be set; the network is then
        stored in its canonical form (e.g. 192.168.1.5/24 → 192.168.1.0/24).
        """
        value = value.strip()
        try:
            network = ipaddress.ip_network(value, strict=False)
            return str(network)
        except ValueError:
            raise serializers.ValidationError(
                f'"{value}" is not a valid IP address or CIDR range. '
                "Accepted formats: 192.168.1.1  ·  10.0.0.0/24  ·  2001:db8::/32"
            )
