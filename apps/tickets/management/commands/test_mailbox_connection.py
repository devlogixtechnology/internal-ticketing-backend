import imaplib
import ssl
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Tests the connection to the dedicated support IMAP mailbox."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Testing IMAP mailbox connection..."))

        server = getattr(settings, 'IMAP_SERVER', 'imap.gmail.com')
        port = getattr(settings, 'IMAP_PORT', 993)
        use_ssl = getattr(settings, 'IMAP_USE_SSL', True)
        username = getattr(settings, 'IMAP_USERNAME', 'laibashafiq634@gmail.com')
        password = getattr(settings, 'IMAP_PASSWORD', 'vssi arwz rmis pebk')
        folder = getattr(settings, 'IMAP_FOLDER', 'INBOX')

        self.stdout.write(f"Connecting to {server}:{port} (SSL: {use_ssl}) as '{username}'...")

        try:
            if use_ssl:
                context = ssl.create_default_context()
                mail = imaplib.IMAP4_SSL(server, port, ssl_context=context)
            else:
                mail = imaplib.IMAP4(server, port)

            # Login attempt
            mail.login(username, password)
            self.stdout.write(self.style.SUCCESS("✓ Authentication successful."))

            # Select Folder
            status, data = mail.select(folder)
            if status == 'OK':
                message_count = data[0].decode('utf-8')
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Mailbox folder '{folder}' selected successfully. Total messages: {message_count}")
                )
            else:
                self.stdout.write(self.style.WARNING(f"⚠ Could not select folder '{folder}'."))

            mail.logout()
            self.stdout.write(self.style.SUCCESS("✓ Dedicated Support Mailbox Connection Test PASSED!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Mailbox connection failed: {str(e)}"))