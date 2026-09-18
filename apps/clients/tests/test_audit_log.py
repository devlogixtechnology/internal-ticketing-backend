from django.test import TestCase

from apps.clients.models import AccessAttemptLog, Client


class AccessAttemptLogTestCase(TestCase):
    def setUp(self):
        self.client = Client.objects.create(name="Audit Client", code="audit")

    def test_creates_and_filters_passed_and_blocked_attempts(self):
        passed = AccessAttemptLog.objects.create(
            client=self.client,
            ip_address="192.0.2.10",
            domain="audit.example.com",
            path="/tickets/",
            status="PASSED",
        )
        blocked = AccessAttemptLog.objects.create(
            ip_address="198.51.100.10",
            path="/admin/",
            status="BLOCKED",
        )

        self.assertEqual(AccessAttemptLog.objects.filter(status="PASSED").count(), 1)
        self.assertEqual(AccessAttemptLog.objects.filter(status="BLOCKED").first(), blocked)
        self.assertEqual(str(passed), "[PASSED] 192.0.2.10 -> /tickets/ (audit)")
        self.assertEqual(str(blocked), "[BLOCKED] 198.51.100.10 -> /admin/ (Unknown)")

    def test_nullable_values_and_default_path_are_supported(self):
        log = AccessAttemptLog.objects.create(status="BLOCKED")

        self.assertIsNone(log.client)
        self.assertEqual(log.path, "/")
        self.assertEqual(str(log), "[BLOCKED] None -> / (Unknown)")