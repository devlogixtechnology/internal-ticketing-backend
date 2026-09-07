"""
test_middleware.py — apps.clients
=================================
Unit tests for TenantWhitelistMiddleware covering:
  a) Allowed domain match
  b) Blocked domain mismatch
  c) Allowed direct IP match
  d) Allowed CIDR subnet IP match (e.g. 10.0.0.5 in 10.0.0.0/24)
  e) Blocked IP outside CIDR range
  f) Invalid IP / Header parsing edge cases
  g) Verified request.client attachment
  h) Excluded / Bypass paths (Django Admin, static, etc.)
  + X-Forwarded-For chain extraction
  + HTTP_REFERER extraction
  + Inactive domain / Inactive client blocking
  + IPv6 direct and CIDR subnet match
"""

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from apps.clients.middleware import TenantWhitelistMiddleware
from apps.clients.models import Client, WhitelistedDomain, WhitelistedIP


def dummy_view(request):
    """Dummy view representing a protected endpoint."""
    return HttpResponse("OK", status=200)


class TenantWhitelistMiddlewareTestCase(TestCase):
    """Comprehensive test suite for TenantWhitelistMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantWhitelistMiddleware(dummy_view)

        # Standard test client
        self.client_a = Client.objects.create(
            name="Acme Corporation",
            code="acme",
            is_active=True,
        )

    # -----------------------------------------------------------------------
    # a) Allowed domain match
    # -----------------------------------------------------------------------
    def test_a_allowed_domain_match(self):
        """Requests with an active whitelisted domain are allowed."""
        WhitelistedDomain.objects.create(
            client=self.client_a,
            domain_name="acme.com",
            is_active=True,
        )

        request = self.factory.get(
            "/tickets/",
            HTTP_ORIGIN="https://acme.com",
            REMOTE_ADDR="198.51.100.1",  # unwhitelisted IP
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
        self.assertEqual(request.client, self.client_a)

    # -----------------------------------------------------------------------
    # b) Blocked domain mismatch
    # -----------------------------------------------------------------------
    def test_b_blocked_domain_mismatch(self):
        """Requests from an unwhitelisted domain are blocked with 403."""
        WhitelistedDomain.objects.create(
            client=self.client_a,
            domain_name="acme.com",
            is_active=True,
        )

        request = self.factory.get(
            "/tickets/",
            HTTP_ORIGIN="https://unauthorized-domain.com",
            REMOTE_ADDR="198.51.100.1",  # unwhitelisted IP
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"403 Access Denied: IP/Domain not whitelisted", response.content)

    # -----------------------------------------------------------------------
    # c) Allowed direct IP match
    # -----------------------------------------------------------------------
    def test_c_allowed_direct_ip_match(self):
        """Requests from an exact whitelisted IP are allowed."""
        WhitelistedIP.objects.create(
            client=self.client_a,
            ip_or_cidr="192.168.1.100",
            description="Office Static IP",
        )

        request = self.factory.get(
            "/tickets/",
            REMOTE_ADDR="192.168.1.100",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.client, self.client_a)

    # -----------------------------------------------------------------------
    # d) Allowed CIDR subnet IP match (e.g., 10.0.0.5 in 10.0.0.0/24)
    # -----------------------------------------------------------------------
    def test_d_allowed_cidr_subnet_ip_match(self):
        """IPs residing within a whitelisted CIDR subnet range are allowed."""
        WhitelistedIP.objects.create(
            client=self.client_a,
            ip_or_cidr="10.0.0.0/24",
            description="Corporate VPN subnet",
        )

        request = self.factory.get(
            "/tickets/",
            REMOTE_ADDR="10.0.0.5",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.client, self.client_a)

    # -----------------------------------------------------------------------
    # e) Blocked IP outside CIDR range
    # -----------------------------------------------------------------------
    def test_e_blocked_ip_outside_cidr_range(self):
        """IPs outside the configured CIDR subnet are rejected with 403."""
        WhitelistedIP.objects.create(
            client=self.client_a,
            ip_or_cidr="10.0.0.0/24",
            description="Corporate VPN subnet",
        )

        request = self.factory.get(
            "/tickets/",
            REMOTE_ADDR="10.0.1.5",  # outside 10.0.0.0/24
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"403 Access Denied: IP/Domain not whitelisted", response.content)

    # -----------------------------------------------------------------------
    # f) Invalid IP / Header parsing edge cases
    # -----------------------------------------------------------------------
    def test_f_invalid_ip_header_parsing_edge_cases(self):
        """Malformed IPs or corrupt headers are handled gracefully without 500 crashes."""
        # 1. Non-existent octet
        req1 = self.factory.get("/tickets/", REMOTE_ADDR="999.999.999.999")
        resp1 = self.middleware(req1)
        self.assertEqual(resp1.status_code, 403)

        # 2. Arbitrary string as IP
        req2 = self.factory.get("/tickets/", REMOTE_ADDR="not-an-ip-address")
        resp2 = self.middleware(req2)
        self.assertEqual(resp2.status_code, 403)

        # 3. Malformed X-Forwarded-For chain
        req3 = self.factory.get(
            "/tickets/",
            HTTP_X_FORWARDED_FOR="bad-ip-string, 10.0.0.1",
        )
        resp3 = self.middleware(req3)
        self.assertEqual(resp3.status_code, 403)

        # 4. Malformed Origin header
        req4 = self.factory.get(
            "/tickets/",
            HTTP_ORIGIN="http://[:::malformed-host",
            REMOTE_ADDR="198.51.100.1",
        )
        resp4 = self.middleware(req4)
        self.assertEqual(resp4.status_code, 403)

    # -----------------------------------------------------------------------
    # g) Verified request.client attachment
    # -----------------------------------------------------------------------
    def test_g_verified_request_client_attachment(self):
        """Verified that the resolved client model instance is attached to request.client."""
        WhitelistedDomain.objects.create(
            client=self.client_a,
            domain_name="portal.acme.com",
            is_active=True,
        )

        request = self.factory.get(
            "/tickets/",
            HTTP_ORIGIN="https://portal.acme.com:8443",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(hasattr(request, "client"))
        self.assertIsNotNone(request.client)
        self.assertEqual(request.client.pk, self.client_a.pk)
        self.assertEqual(request.client.code, "acme")
        self.assertEqual(request.client.name, "Acme Corporation")

    # -----------------------------------------------------------------------
    # h) Excluded / Bypass paths (like Django Admin or public routes)
    # -----------------------------------------------------------------------
    def test_h_excluded_bypass_paths(self):
        """Requests to exempt paths bypass whitelist checks and set request.client to None."""
        # 1. Django Admin root
        req1 = self.factory.get("/admin/", REMOTE_ADDR="198.51.100.99")
        resp1 = self.middleware(req1)
        self.assertEqual(resp1.status_code, 200)
        self.assertIsNone(req1.client)

        # 2. Django Admin subpath
        req2 = self.factory.get("/admin/login/", REMOTE_ADDR="198.51.100.99")
        resp2 = self.middleware(req2)
        self.assertEqual(resp2.status_code, 200)
        self.assertIsNone(req2.client)

        # 3. Static assets
        req3 = self.factory.get("/static/css/base.css", REMOTE_ADDR="198.51.100.99")
        resp3 = self.middleware(req3)
        self.assertEqual(resp3.status_code, 200)

        # 4. Media assets
        req4 = self.factory.get("/media/uploads/logo.png", REMOTE_ADDR="198.51.100.99")
        resp4 = self.middleware(req4)
        self.assertEqual(resp4.status_code, 200)

    # -----------------------------------------------------------------------
    # Additional robust tests
    # -----------------------------------------------------------------------
    def test_x_forwarded_for_first_ip_extraction(self):
        """Client IP is properly extracted from the beginning of an X-Forwarded-For proxy chain."""
        WhitelistedIP.objects.create(
            client=self.client_a,
            ip_or_cidr="172.16.50.0/24",
            description="Branch Office",
        )

        request = self.factory.get(
            "/tickets/",
            HTTP_X_FORWARDED_FOR="172.16.50.42, 10.200.0.1, 192.168.0.1",
            REMOTE_ADDR="10.200.0.1",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.client, self.client_a)

    def test_referer_header_domain_extraction(self):
        """Extracts domain from HTTP_REFERER when HTTP_ORIGIN is absent."""
        WhitelistedDomain.objects.create(
            client=self.client_a,
            domain_name="helpdesk.acme.org",
            is_active=True,
        )

        request = self.factory.get(
            "/tickets/",
            HTTP_REFERER="https://helpdesk.acme.org/portal/tickets/view/100/",
            REMOTE_ADDR="198.51.100.1",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.client, self.client_a)

    def test_inactive_domain_or_inactive_client_blocked(self):
        """Inactive domains or domains belonging to inactive clients are rejected."""
        # 1. Inactive domain on active client
        WhitelistedDomain.objects.create(
            client=self.client_a,
            domain_name="deactivated.acme.com",
            is_active=False,
        )
        req1 = self.factory.get(
            "/tickets/",
            HTTP_ORIGIN="https://deactivated.acme.com",
            REMOTE_ADDR="198.51.100.1",
        )
        resp1 = self.middleware(req1)
        self.assertEqual(resp1.status_code, 403)

        # 2. Active domain on inactive client
        inactive_client = Client.objects.create(
            name="Suspended Client",
            code="suspended",
            is_active=False,
        )
        WhitelistedDomain.objects.create(
            client=inactive_client,
            domain_name="suspended.com",
            is_active=True,
        )
        req2 = self.factory.get(
            "/tickets/",
            HTTP_ORIGIN="https://suspended.com",
            REMOTE_ADDR="198.51.100.1",
        )
        resp2 = self.middleware(req2)
        self.assertEqual(resp2.status_code, 403)

    def test_ipv6_direct_and_cidr_match(self):
        """IPv6 plain addresses and IPv6 CIDR subnets are correctly matched."""
        WhitelistedIP.objects.create(
            client=self.client_a,
            ip_or_cidr="2001:db8:abcd::/48",
            description="IPv6 Range",
        )

        # Matched IPv6 inside subnet
        req1 = self.factory.get(
            "/tickets/",
            REMOTE_ADDR="2001:db8:abcd::1",
        )
        resp1 = self.middleware(req1)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(req1.client, self.client_a)

        # Unmatched IPv6 outside subnet
        req2 = self.factory.get(
            "/tickets/",
            REMOTE_ADDR="2001:db8:ffff::1",
        )
        resp2 = self.middleware(req2)
        self.assertEqual(resp2.status_code, 403)

    def test_explicit_client_is_used_before_headers(self):
        """An upstream middleware client is authoritative for resolution."""
        other_client = Client.objects.create(name="Other Corporation", code="other")
        request = self.factory.get(
            "/tickets/",
            HTTP_X_CLIENT_CODE="other",
            REMOTE_ADDR="198.51.100.20",
        )
        request.client = self.client_a

        self.assertIs(self.middleware.resolve_client(request), self.client_a)

    def test_alternate_client_headers_and_invalid_id_fall_through(self):
        """Supported aliases resolve clients and invalid IDs do not raise."""
        request = self.factory.get("/tickets/", HTTP_X_TENANT_CODE="ACME")
        self.assertEqual(self.middleware.resolve_client(request), self.client_a)

        request = self.factory.get("/tickets/", HTTP_X_TENANT_ID="not-an-integer")
        self.assertIsNone(self.middleware.resolve_client(request))

    def test_domain_falls_back_to_client_code(self):
        """A bare request domain can resolve an active client code."""
        request = self.factory.get("/tickets/", HTTP_ORIGIN="https://ACME")
        self.assertEqual(self.middleware.resolve_client(request, domain="acme"), self.client_a)

    def test_invalid_stored_cidr_is_skipped(self):
        """A legacy malformed whitelist entry cannot break request handling."""
        WhitelistedIP.objects.create(
            client=self.client_a,
            ip_or_cidr="10.0.0.0/24",
        )
        WhitelistedIP.objects.filter(client=self.client_a).update(ip_or_cidr="not-a-network")

        request = self.factory.get("/tickets/", REMOTE_ADDR="10.0.0.5")
        response = self.middleware(request)

        self.assertEqual(response.status_code, 403)

    def test_invalid_and_empty_header_values_are_safe(self):
        """Blank headers and malformed URL/IP values return None cleanly."""
        request = self.factory.get(
            "/tickets/",
            HTTP_ORIGIN="   ",
            HTTP_REFERER="   ",
            HTTP_X_FORWARDED_FOR=" ,  ",
            REMOTE_ADDR="   ",
        )

        self.assertIsNone(self.middleware.extract_domain(request))
        self.assertIsNone(self.middleware.extract_client_ip(request))
        self.assertIsNone(self.middleware._clean_ip_for_log("invalid"))
        self.assertIsNone(self.middleware._match_ip("invalid"))

    def test_conflicting_domain_and_ip_belongs_to_same_resolved_client(self):
        """A resolved client prevents a different domain/IP tenant from passing."""
        other_client = Client.objects.create(name="Other Corporation", code="other")
        WhitelistedDomain.objects.create(client=other_client, domain_name="other.com")
        WhitelistedIP.objects.create(client=self.client_a, ip_or_cidr="10.0.0.0/24")

        request = self.factory.get(
            "/tickets/",
            HTTP_ORIGIN="https://other.com",
            REMOTE_ADDR="10.0.0.5",
            HTTP_X_CLIENT_CODE="acme",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.client, self.client_a)

    @override_settings(TENANT_WHITELIST_EXEMPT_PATHS=["/public/"])
    def test_custom_exempt_paths_replace_defaults(self):
        """Configured exempt paths are honored and do not create audit logs."""
        request = self.factory.get("/public/status/", REMOTE_ADDR="invalid")
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(request.client)
