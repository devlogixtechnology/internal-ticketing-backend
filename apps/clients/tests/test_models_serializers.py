from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.exceptions import ValidationError as SerializerValidationError

from apps.clients.models import Client, WhitelistedDomain, WhitelistedIP, validate_ip_or_cidr
from apps.clients.serializers import (
    ClientOnboardingSerializer,
    ClientSerializer,
    WhitelistedDomainSerializer,
    WhitelistedIPSerializer,
)


class ClientModelAndSerializerTestCase(TestCase):
    def setUp(self):
        self.client = Client.objects.create(name="Model Client", code="model-client")

    def test_client_generates_code_and_formats_as_string(self):
        generated = Client.objects.create(name="Generated Client")

        self.assertEqual(generated.code, "generated-client")
        self.assertEqual(str(generated), "Generated Client (generated-client)")

    def test_ip_validator_accepts_ip_and_cidr_and_rejects_invalid_value(self):
        validate_ip_or_cidr("192.0.2.1")
        validate_ip_or_cidr("10.0.0.5/24")

        with self.assertRaises(ValidationError):
            validate_ip_or_cidr("not-an-ip")

    def test_whitelist_models_format_status_and_description(self):
        domain = WhitelistedDomain.objects.create(client=self.client, domain_name="example.com")
        ip = WhitelistedIP.objects.create(
            client=self.client,
            ip_or_cidr="192.0.2.1",
            description="Office",
        )

        self.assertIn("example.com", str(domain))
        self.assertIn("192.0.2.1", str(ip))
        self.assertIn("Office", str(ip))
        domain.is_active = False
        self.assertIn("x", str(domain))

    def test_client_serializer_serializes_read_only_fields(self):
        data = ClientSerializer(self.client).data

        self.assertEqual(data["code"], "model-client")
        self.assertEqual(data["name"], "Model Client")
        self.assertIn("created_at", data)

    def test_domain_serializer_normalizes_and_rejects_unsafe_domains(self):
        serializer = WhitelistedDomainSerializer()
        self.assertEqual(serializer.validate_domain_name(" @Example.COM "), "example.com")

        for value in ("https://example.com", "example.com/path", "localhost"):
            with self.assertRaises(SerializerValidationError):
                serializer.validate_domain_name(value)

    def test_ip_serializer_normalizes_and_rejects_invalid_values(self):
        serializer = WhitelistedIPSerializer()
        self.assertEqual(serializer.validate_ip_or_cidr(" 10.0.0.5/24 "), "10.0.0.0/24")

        with self.assertRaises(SerializerValidationError):
            serializer.validate_ip_or_cidr("not-an-ip")

    def test_onboarding_serializer_validates_optional_whitelist_fields(self):
        serializer = ClientOnboardingSerializer(data={
            "client_name": "Onboarded",
            "contact_name": "Owner",
            "contact_email": "owner@example.com",
            "domain_name": " @Example.COM ",
            "ip_or_cidr": "10.0.0.5/24",
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["domain_name"], "example.com")
        self.assertEqual(serializer.validated_data["ip_or_cidr"], "10.0.0.0/24")