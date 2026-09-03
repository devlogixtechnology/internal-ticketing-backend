"""
middleware.py — apps.clients
============================
Tenant Whitelist Middleware:
  1. Bypasses configured exempt paths (e.g. Django Admin, static, media, etc.).
  2. Extracts client IP from HTTP_X_FORWARDED_FOR or REMOTE_ADDR.
  3. Extracts domain from HTTP_ORIGIN or HTTP_REFERER.
  4. Matches extracted domain against WhitelistedDomain and IP against
     WhitelistedIP (supporting CIDR subnets via python's ipaddress module).
  5. If matched, attaches resolved client to request.client.
  6. If unauthorized or unmatched, returns HttpResponseForbidden (403).
"""

import ipaddress
import logging
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponseForbidden

from .models import WhitelistedDomain, WhitelistedIP

logger = logging.getLogger(__name__)

DEFAULT_EXEMPT_PATHS = [
    "/admin/",
    "/static/",
    "/media/",
]


class TenantWhitelistMiddleware:
    """
    Middleware that validates incoming HTTP requests against
    whitelisted domains and IP addresses/CIDR subnets.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    @property
    def exempt_paths(self):
        """Allow dynamic configuration of exempt paths via Django settings."""
        return getattr(settings, "TENANT_WHITELIST_EXEMPT_PATHS", DEFAULT_EXEMPT_PATHS)

    def __call__(self, request):
        path = request.path_info

        # 1. Check for bypass / exempt paths
        for exempt_prefix in self.exempt_paths:
            if path.startswith(exempt_prefix):
                request.client = None
                return self.get_response(request)

        # 2. Extract domain and IP from headers
        domain = self.extract_domain(request)
        client_ip_str = self.extract_client_ip(request)

        client = None

        # 3. Match extracted domain if present
        if domain:
            client = self._match_domain(domain)

        # 4. If domain didn't resolve a client, match IP / CIDR
        if not client and client_ip_str:
            client = self._match_ip(client_ip_str)

        # 5. Attach client if authorized
        if client:
            request.client = client
            return self.get_response(request)

        # 6. Unauthorized access
        logger.warning(
            "Tenant access denied. Path: %s, Domain: %s, IP: %s",
            path,
            domain,
            client_ip_str,
        )
        return HttpResponseForbidden("403 Access Denied: IP/Domain not whitelisted")

    @staticmethod
    def extract_domain(request):
        """
        Extract bare domain/host from HTTP_ORIGIN or HTTP_REFERER.
        Strips scheme, port, and path.
        """
        raw = request.META.get("HTTP_ORIGIN")
        if not raw or not raw.strip():
            raw = request.META.get("HTTP_REFERER")

        if not raw or not raw.strip():
            return None

        raw = raw.strip()
        if "://" not in raw:
            raw = f"http://{raw}"

        try:
            parsed = urlparse(raw)
            if parsed.hostname:
                return parsed.hostname.lower().strip()
        except Exception:
            return None

        return None

    @staticmethod
    def extract_client_ip(request):
        """
        Extract client IP from HTTP_X_FORWARDED_FOR (first IP in chain)
        or fall back to REMOTE_ADDR.
        """
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for and x_forwarded_for.strip():
            parts = [p.strip().strip("'\"[]") for p in x_forwarded_for.split(",") if p.strip()]
            if parts:
                return parts[0]

        remote_addr = request.META.get("REMOTE_ADDR")
        if remote_addr and remote_addr.strip():
            return remote_addr.strip().strip("'\"[]")

        return None

    @staticmethod
    def _match_domain(domain: str):
        """
        Match domain against active WhitelistedDomain records
        belonging to active Clients.
        """
        wl_domain = (
            WhitelistedDomain.objects.filter(
                domain_name__iexact=domain,
                is_active=True,
                client__is_active=True,
            )
            .select_related("client")
            .first()
        )
        if wl_domain:
            return wl_domain.client
        return None

    @staticmethod
    def _match_ip(ip_str: str):
        """
        Match IP string against active WhitelistedIP records
        (supporting both plain IPs and CIDR ranges) belonging to active Clients.
        """
        try:
            client_ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return None

        whitelisted_ips = (
            WhitelistedIP.objects.filter(client__is_active=True)
            .select_related("client")
        )

        for entry in whitelisted_ips:
            try:
                network = ipaddress.ip_network(entry.ip_or_cidr.strip(), strict=False)
                if client_ip.version == network.version and client_ip in network:
                    return entry.client
            except ValueError:
                continue

        return None
