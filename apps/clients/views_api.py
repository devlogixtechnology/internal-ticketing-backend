from django.db import transaction
from django.core.mail import send_mail
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from .models import Client, ClientContact, WhitelistedDomain


class OnboardRateThrottle(UserRateThrottle):
    # 10 requests per minute limit set ki gayi hai
    rate = '10/minute'


class ClientOnboardAPIView(APIView):
    # Rate limiting apply karein taake 11th request par 429 status code mile
    throttle_classes = [OnboardRateThrottle]

    def post(self, request, *args, **kwargs):
        data = request.data
        client_name = data.get("client_name")
        contact_name = data.get("contact_name")
        contact_email = data.get("contact_email")
        domain_name = data.get("domain_name")

        # Basic validation
        if not client_name or not contact_email:
            return Response(
                {"error": "client_name and contact_email are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Atomic block: Agar email failure ya koi error aaye to DB rollback ho jaye
            with transaction.atomic():
                client = Client.objects.create(name=client_name)

                ClientContact.objects.create(
                    client=client,
                    name=contact_name,
                    email=contact_email
                )

                if domain_name:
                    WhitelistedDomain.objects.create(
                        client=client,
                        domain_name=domain_name
                    )

                # Email trigger (agar yeh fail hota hai to exception raise hoga aur DB rollback ho jayega)
                send_mail(
                    subject="Welcome to Platform",
                    message=f"Hello {contact_name}, your client account has been created.",
                    from_email="noreply@example.com",
                    recipient_list=[contact_email],
                    fail_silently=False,
                )

        except Exception as e:
            # Email ya creation failure par HTTP 400 Bad Request return hoga
            return Response(
                {"error": f"Failed to onboard client: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"message": "Client onboarded successfully."},
            status=status.HTTP_201_CREATED
        )