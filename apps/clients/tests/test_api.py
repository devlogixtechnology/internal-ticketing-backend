from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.clients.models import Client, ClientContact, WhitelistedDomain

User = get_user_model()


class ClientOnboardAPITest(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.admin_user = User.objects.create_superuser(
            username="admin", 
            email="admin@test.com", 
            password="password123"
        )
        self.client_api.force_authenticate(user=self.admin_user)
        
        # Agar app_name = "clients" defined hai urls.py mein to namespace use karein:
        try:
            self.url = reverse("clients:client-onboard")
        except Exception:
            self.url = reverse("client-onboard")

    @patch("apps.clients.views_api.send_mail")
    def test_atomic_rollback_on_email_failure(self, mock_send_mail):
        """Ensure DB rolls back completely (Client, Contact, Whitelist) if send_mail raises an exception."""
        mock_send_mail.side_effect = Exception("SMTP Server Connection Error")

        payload = {
            "client_name": "Test Rollback Client",
            "contact_name": "John Doe",
            "contact_email": "john@example.com",
            "domain_name": "testclient.com"
        }

        response = self.client_api.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Client.objects.filter(name="Test Rollback Client").count(), 0)
        self.assertEqual(ClientContact.objects.filter(email="john@example.com").count(), 0)
        self.assertEqual(WhitelistedDomain.objects.filter(domain_name="testclient.com").count(), 0)

    def test_throttling_11th_request(self):
        """Ensure 11th request within 1 min returns 429 Too Many Requests."""
        payload = {
            "client_name": "Throttle Client",
            "contact_name": "John",
            "contact_email": "john@example.com"
        }

        with patch("apps.clients.views_api.send_mail"):
            for _ in range(10):
                self.client_api.post(self.url, payload, format="json")

            response_11th = self.client_api.post(self.url, payload, format="json")

        self.assertEqual(response_11th.status_code, status.HTTP_429_TOO_MANY_REQUESTS)