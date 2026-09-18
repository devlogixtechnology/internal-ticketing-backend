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

from .models import AccessAttemptLog, Client, WhitelistedDomain, WhitelistedIP

logger = logging.getLogger(__name__)

DEFAULT_EXEMPT_PATHS = [
    "/admin/",
    "/static/",
    "/media/",
    "/api/admin/clients/onboard/",
]


class TenantWhitelistMiddleware:
    """
    Middleware that validates incoming HTTP requests against
    whitelisted domains and IP addresses/CIDR subnets, supporting
    Grace Mode (enforce_whitelisting=False) and access audit logging.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    @property
    def exempt_paths(self):
        """Allow dynamic configuration of exempt paths via Django settings."""
        return getattr(settings, "TENANT_WHITELIST_EXEMPT_PATHS", DEFAULT_EXEMPT_PATHS)

    def __call__(self, request):
        path = request.path_info or "/"

        # 1. Check for bypass / exempt paths
        for exempt_prefix in self.exempt_paths:
            if path.startswith(exempt_prefix):
                request.client = None
                return self.get_response(request)

        # 2. Extract request IP, domain, and path
        domain = self.extract_domain(request)
        client_ip_str = self.extract_client_ip(request)

        # 3. Resolve the client based on domain/header
        client = self.resolve_client(request, domain=domain, client_ip_str=client_ip_str)

        # 4. Determine if access is valid based on existing whitelist rules
        is_valid = False
        if domain:
            domain_client = self._match_domain(domain)
            if domain_client and (client is None or domain_client.pk == client.pk):
                is_valid = True
                if not client:
                    client = domain_client

        if not is_valid and client_ip_str:
            ip_client = self._match_ip(client_ip_str)
            if ip_client and (client is None or ip_client.pk == client.pk):
                is_valid = True
                if not client:
                    client = ip_client

        # 5. Check Grace Mode:
        # If IP/domain is valid OR if client.enforce_whitelisting is False:
        #   Log 'PASSED' and allow access.
        # If IP/domain is invalid AND (client is None or client.enforce_whitelisting is True):
        #   Log 'BLOCKED' and return 403 Forbidden.
        if is_valid or (client and not client.enforce_whitelisting):
            request.client = client
            AccessAttemptLog.objects.create(
                client=client,
                ip_address=self._clean_ip_for_log(client_ip_str),
                domain=domain[:255] if domain else None,
                path=path[:255],
                status="PASSED",
            )
            return self.get_response(request)

        # Unauthorized access
        AccessAttemptLog.objects.create(
            client=client,
            ip_address=self._clean_ip_for_log(client_ip_str),
            domain=domain[:255] if domain else None,
            path=path[:255],
            status="BLOCKED",
        )
        logger.warning(
            "Tenant access denied. Path: %s, Domain: %s, IP: %s, Client: %s",
            path,
            domain,
            client_ip_str,
            client,
        )
        return HttpResponseForbidden("403 Access Denied: IP/Domain not whitelisted. Tenant access denied.")

    def resolve_client(self, request, domain=None, client_ip_str=None):
        """
        Resolve the client entity using:
        1. Explicit request.client if already present
        2. Headers: X-Client-Code, X-Tenant-Code, X-Client, X-Tenant, X-Client-ID, X-Tenant-ID
        3. Extracted domain (matching WhitelistedDomain or Client.code)
        4. Extracted client IP (matching WhitelistedIP)
        """
        if getattr(request, "client", None):
            return request.client

        # Header resolution by code
        client_code = (
            request.META.get("HTTP_X_CLIENT_CODE")
            or request.META.get("HTTP_X_TENANT_CODE")
            or request.META.get("HTTP_X_CLIENT")
            or request.META.get("HTTP_X_TENANT")
        )
        if client_code and str(client_code).strip():
            client = Client.objects.filter(code__iexact=str(client_code).strip(), is_active=True).first()
            if client:
                return client

        # Header resolution by ID
        client_id = request.META.get("HTTP_X_CLIENT_ID") or request.META.get("HTTP_X_TENANT_ID")
        if client_id and str(client_id).strip():
            try:
                client = Client.objects.filter(pk=int(str(client_id).strip()), is_active=True).first()
                if client:
                    return client
            except (ValueError, TypeError):
                pass

        # Domain resolution
        if domain:
            client = self._match_domain(domain)
            if client:
                return client
            client = Client.objects.filter(code__iexact=domain, is_active=True).first()
            if client:
                return client

        # IP resolution
        if client_ip_str:
            client = self._match_ip(client_ip_str)
            if client:
                return client

        return None

    @staticmethod
    def _clean_ip_for_log(ip_str):
        """Validate and return clean IP string for GenericIPAddressField, or None if invalid."""
        if not ip_str:
            return None
        try:
            ipaddress.ip_address(ip_str.strip())
            return ip_str.strip()
        except ValueError:
            return None

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
