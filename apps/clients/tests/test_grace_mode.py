"""
test_grace_mode.py — apps.clients
=================================
Unit tests for BE5: Grace Mode & Access Audit Log.
Verifies:
  1. Grace Mode ON (enforce_whitelisting=True): un-whitelisted IP gets blocked (403) and logged as BLOCKED.
  2. Grace Mode OFF (enforce_whitelisting=False): un-whitelisted IP gets allowed (200) and logged as PASSED.
  3. Acceptance test: 20 simulated requests across configurations asserting accurate DB log entries.
"""

from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.clients.middleware import TenantWhitelistMiddleware
from apps.clients.models import AccessAttemptLog, Client, WhitelistedDomain, WhitelistedIP


def dummy_view(request):
    """Dummy protected view for middleware testing."""
    return HttpResponse("OK", status=200)


class GraceModeTestCase(TestCase):
    """Test suite for Grace Mode toggle and AccessAttemptLog creation."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantWhitelistMiddleware(dummy_view)

        # Tenant 1: Strict mode (Grace Mode OFF)
        self.client_enforced = Client.objects.create(
            name="Strict Corp",
            code="strict-corp",
            is_active=True,
            enforce_whitelisting=True,
        )
        self.wl_ip_enforced = WhitelistedIP.objects.create(
            client=self.client_enforced,
            ip_or_cidr="192.168.1.100",
            description="Office Static IP",
        )
        self.wl_domain_enforced = WhitelistedDomain.objects.create(
            client=self.client_enforced,
            domain_name="strict.example.com",
            is_active=True,
        )

        # Tenant 2: Grace Mode ON (enforce_whitelisting=False)
        self.client_grace = Client.objects.create(
            name="Grace Corp",
            code="grace-corp",
            is_active=True,
            enforce_whitelisting=False,
        )
        self.wl_ip_grace = WhitelistedIP.objects.create(
            client=self.client_grace,
            ip_or_cidr="10.20.30.40",
            description="Grace Authorized IP",
        )
        self.wl_domain_grace = WhitelistedDomain.objects.create(
            client=self.client_grace,
            domain_name="grace.example.com",
            is_active=True,
        )

    # -----------------------------------------------------------------------
    # Requirement: Test Grace Mode ON (enforce_whitelisting=True)
    # Un-whitelisted IP gets blocked (403) and logged as BLOCKED.
    # -----------------------------------------------------------------------
    def test_grace_mode_on_unwhitelisted_ip_blocked(self):
        """Un-whitelisted IP on strict client is blocked with 403 and logged as BLOCKED."""
        request = self.factory.get(
            "/tickets/dashboard/",
            REMOTE_ADDR="198.51.100.22",
            HTTP_X_CLIENT_CODE="strict-corp",
        )
        response = self.middleware(request)

        # Verify 403 Forbidden
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"403 Access Denied", response.content)

        # Verify AccessAttemptLog
        log = AccessAttemptLog.objects.latest("created_at")
        self.assertEqual(log.client, self.client_enforced)
        self.assertEqual(log.ip_address, "198.51.100.22")
        self.assertEqual(log.path, "/tickets/dashboard/")
        self.assertEqual(log.status, "BLOCKED")

    # -----------------------------------------------------------------------
    # Requirement: Test Grace Mode OFF (enforce_whitelisting=False)
    # Un-whitelisted IP gets allowed (200) and logged as PASSED.
    # -----------------------------------------------------------------------
    def test_grace_mode_off_unwhitelisted_ip_allowed(self):
        """Un-whitelisted IP on grace mode client is allowed (200) and logged as PASSED."""
        request = self.factory.get(
            "/tickets/dashboard/",
            REMOTE_ADDR="198.51.100.33",
            HTTP_X_CLIENT_CODE="grace-corp",
        )
        response = self.middleware(request)

        # Verify 200 OK and client attachment
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
        self.assertEqual(request.client, self.client_grace)

        # Verify AccessAttemptLog
        log = AccessAttemptLog.objects.latest("created_at")
        self.assertEqual(log.client, self.client_grace)
        self.assertEqual(log.ip_address, "198.51.100.33")
        self.assertEqual(log.path, "/tickets/dashboard/")
        self.assertEqual(log.status, "PASSED")

    # -----------------------------------------------------------------------
    # Requirement: Whitelisted IP allows access when enforce_whitelisting=True
    # -----------------------------------------------------------------------
    def test_whitelisted_ip_allowed_when_strict(self):
        """Whitelisted IP on strict client is allowed (200) and logged as PASSED."""
        request = self.factory.get(
            "/tickets/dashboard/",
            REMOTE_ADDR="192.168.1.100",
            HTTP_X_CLIENT_CODE="strict-corp",
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.client, self.client_enforced)

        log = AccessAttemptLog.objects.latest("created_at")
        self.assertEqual(log.client, self.client_enforced)
        self.assertEqual(log.ip_address, "192.168.1.100")
        self.assertEqual(log.status, "PASSED")

    # -----------------------------------------------------------------------
    # Requirement: Acceptance Test (Simulate 20 requests)
    # Mix of valid/invalid IPs across different enforce settings asserting
    # exactly 20 corresponding AccessAttemptLog rows exist with accurate statuses.
    # -----------------------------------------------------------------------
    def test_acceptance_twenty_simulated_requests(self):
        """
        Simulate 20 requests with a mix of:
        - 5 valid IPs on enforced client -> PASSED (200)
        - 5 invalid IPs on enforced client -> BLOCKED (403)
        - 5 valid IPs on grace client -> PASSED (200)
        - 5 invalid IPs on grace client -> PASSED (200)

        Asserts exactly 20 AccessAttemptLog rows are created with accurate status values.
        """
        AccessAttemptLog.objects.all().delete()

        simulated_scenarios = [
            # Group 1: 5 Valid IPs on enforced client -> PASSED
            {"client": self.client_enforced, "ip": "192.168.1.100", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_enforced, "ip": "192.168.1.100", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_enforced, "ip": "192.168.1.100", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_enforced, "ip": "192.168.1.100", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_enforced, "ip": "192.168.1.100", "expected_status": "PASSED", "expected_code": 200},

            # Group 2: 5 Invalid IPs on enforced client -> BLOCKED
            {"client": self.client_enforced, "ip": "203.0.113.1", "expected_status": "BLOCKED", "expected_code": 403},
            {"client": self.client_enforced, "ip": "203.0.113.2", "expected_status": "BLOCKED", "expected_code": 403},
            {"client": self.client_enforced, "ip": "203.0.113.3", "expected_status": "BLOCKED", "expected_code": 403},
            {"client": self.client_enforced, "ip": "203.0.113.4", "expected_status": "BLOCKED", "expected_code": 403},
            {"client": self.client_enforced, "ip": "203.0.113.5", "expected_status": "BLOCKED", "expected_code": 403},

            # Group 3: 5 Valid IPs on grace client -> PASSED
            {"client": self.client_grace, "ip": "10.20.30.40", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_grace, "ip": "10.20.30.40", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_grace, "ip": "10.20.30.40", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_grace, "ip": "10.20.30.40", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_grace, "ip": "10.20.30.40", "expected_status": "PASSED", "expected_code": 200},

            # Group 4: 5 Invalid IPs on grace client -> PASSED (Grace Mode Active)
            {"client": self.client_grace, "ip": "198.51.100.11", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_grace, "ip": "198.51.100.12", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_grace, "ip": "198.51.100.13", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_grace, "ip": "198.51.100.14", "expected_status": "PASSED", "expected_code": 200},
            {"client": self.client_grace, "ip": "198.51.100.15", "expected_status": "PASSED", "expected_code": 200},
        ]

        self.assertEqual(len(simulated_scenarios), 20)

        for index, scenario in enumerate(simulated_scenarios, start=1):
            path = f"/api/tickets/simulation-{index}/"
            req = self.factory.get(
                path,
                REMOTE_ADDR=scenario["ip"],
                HTTP_X_CLIENT_CODE=scenario["client"].code,
            )
            resp = self.middleware(req)
            self.assertEqual(
                resp.status_code,
                scenario["expected_code"],
                f"Request #{index} (IP: {scenario['ip']}, Client: {scenario['client'].code}) expected HTTP {scenario['expected_code']}, got {resp.status_code}",
            )

        # Assert exactly 20 corresponding AccessAttemptLog rows exist in the database
        total_logs = AccessAttemptLog.objects.count()
        self.assertEqual(total_logs, 20, f"Expected exactly 20 log records, found {total_logs}")

        # Assert status counts
        passed_count = AccessAttemptLog.objects.filter(status="PASSED").count()
        blocked_count = AccessAttemptLog.objects.filter(status="BLOCKED").count()
        self.assertEqual(passed_count, 15, f"Expected 15 PASSED logs, found {passed_count}")
        self.assertEqual(blocked_count, 5, f"Expected 5 BLOCKED logs, found {blocked_count}")
