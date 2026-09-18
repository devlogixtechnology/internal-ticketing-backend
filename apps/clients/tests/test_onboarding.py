from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.clients.models import Client

class OnboardingTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('clients:client-onboard-api')

    def test_throttling_11th_request(self):
        payload = {
            "name": "Test Client", 
            "code": "TC1", 
            "email": "test@example.com", 
            "contact_name": "John Doe"
        }
        for _ in range(10):
            self.client.post(self.url, payload, format='json')
        
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_atomic_rollback(self):
        payload = {
            "name": "Fail Test", 
            "code": "FAIL1", 
            "email": "invalid-email", 
            "contact_name": "John Doe"
        }
        self.client.post(self.url, payload, format='json')
        self.assertEqual(Client.objects.filter(code="FAIL1").count(), 0)