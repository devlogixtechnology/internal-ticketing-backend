import imaplib
import email
from email.header import decode_header
import ssl
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from apps.tickets.models import Ticket, Category, TicketAttachment
from apps.clients.models import WhitelistedEmergencyEmail

User = get_user_model()


class Command(BaseCommand):
    help = "Ingests unread emails from the dedicated support IMAP mailbox and creates tickets with attachments."

    def clean_html(self, raw_html):
        """Simple helper to strip basic HTML tags if plain text is missing."""
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext.strip()

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting inbound email ingestion with body & attachment parsing..."))

        server = getattr(settings, 'IMAP_SERVER', 'imap.gmail.com')
        port = getattr(settings, 'IMAP_PORT', 993)
        username = getattr(settings, 'IMAP_USERNAME', '')
        password = getattr(settings, 'IMAP_PASSWORD', '')
        folder = getattr(settings, 'IMAP_FOLDER', 'INBOX')

        # 1. Resolve or create Default System User
        system_user = User.objects.filter(is_superuser=True).first()
        if not system_user:
            system_user = User.objects.first()
        if not system_user:
            system_user = User.objects.create_user(
                username="email_system_bot",
                email="system@local.bot",
                password="SystemPassword123!"
            )

        # 2. Resolve Default Category
        default_category, _ = Category.objects.get_or_create(
            name="Email Ingestion",
            defaults={"description": "Default category for auto-ingested support emails"}
        )

        mail = None
        try:
            context = ssl.create_default_context()
            mail = imaplib.IMAP4_SSL(server, port, ssl_context=context, timeout=30)
            mail.login(username, password)
            mail.select(folder)

            # Search for UNSEEN emails
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK' or not messages[0]:
                self.stdout.write(self.style.SUCCESS("No new unread emails found."))
                return

            email_ids = messages[0].split()
            total_emails = len(email_ids)
            self.stdout.write(f"Found {total_emails} new email(s) to process.")

            # Process batch of 10 emails
            for e_id in email_ids[:10]:
                status, msg_data = mail.fetch(e_id, '(RFC822)')
                if status != 'OK' or not msg_data:
                    continue

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # Subject parsing
                        subject, encoding = decode_header(msg.get("Subject", ""))[0] if msg.get("Subject") else ("Inbound Email Ticket", None)
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8", errors="ignore")
                        
                        # From parsing
                        from_address = email.utils.parseaddr(msg.get("From"))[1]

                        # Body and Attachments Parsing Variables
                        body_plain = ""
                        body_html = ""
                        attachments_data = []  # List of tuples: (filename, file_content)

                        if msg.is_multipart():
                            for part in msg.walk():
                                # Multipart root container ignore karein
                                if part.get_content_maintype() == 'multipart':
                                    continue

                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition", ""))
                                filename = part.get_filename()

                                # Decode filename if encoded
                                if filename:
                                    filename_decoded, fname_encoding = decode_header(filename)[0]
                                    if isinstance(filename_decoded, bytes):
                                        filename = filename_decoded.decode(fname_encoding or "utf-8", errors="ignore")

                                # Check if part is an attachment, inline file, or image
                                is_attachment = "attachment" in content_disposition or "inline" in content_disposition or filename
                                is_image = content_type.startswith("image/")

                                if is_attachment or is_image:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        # Fallback filename generated agar image ka naam nahi mil raha
                                        if not filename:
                                            ext = content_type.split('/')[-1] if '/' in content_type else 'png'
                                            filename = f"inline_image.{ext}"

                                        attachments_data.append((filename, payload))
                                
                                # Extract Body (Plain text preferred, HTML fallback)
                                elif content_type == "text/plain" and not body_plain:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body_plain = payload.decode(errors="ignore")
                                elif content_type == "text/html" and not body_html:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body_html = payload.decode(errors="ignore")
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                if msg.get_content_type() == "text/html":
                                    body_html = payload.decode(errors="ignore")
                                else:
                                    body_plain = payload.decode(errors="ignore")

                        # Finalize ticket description body
                        final_body = body_plain or self.clean_html(body_html) or 'No body content provided.'

                        # Emergency check
                        is_whitelisted = False
                        matched_emergency_entry = None
                        if from_address:
                            matched_emergency_entry = WhitelistedEmergencyEmail.objects.filter(
                                email__iexact=from_address,
                                verified=True
                            ).first()
                            if matched_emergency_entry:
                                is_whitelisted = True

                        ticket_title = f"{'[EMERGENCY] ' if is_whitelisted else ''}{subject or 'Inbound Email Ticket'}"
                        ticket_desc = (
                            f"From: {from_address}\n"
                            f"Emergency Whitelisted: {is_whitelisted}\n"
                            f"Purpose: {matched_emergency_entry.purpose if matched_emergency_entry else 'N/A'}\n\n"
                            f"{final_body}"
                        )

                        # Create Ticket
                        ticket = Ticket.objects.create(
                            title=ticket_title[:255],
                            description=ticket_desc,
                            category=default_category,
                            created_by=system_user,
                            status="OPEN",
                            priority="CRITICAL" if is_whitelisted else "MEDIUM"
                        )

                        # Save extracted Attachments/Inline Images into TicketAttachment Model
                        saved_attachments_count = 0
                        for fname, content in attachments_data:
                            django_file = ContentFile(content, name=fname)
                            TicketAttachment.objects.create(
                                ticket=ticket,
                                file=django_file,
                                uploaded_by=system_user  # <-- Yeh line yahan majood honi chahiye
                            )
                            saved_attachments_count += 1
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ Created Ticket ID #{ticket.id} for '{from_address}' "
                                f"(Emergency: {is_whitelisted}, Attachments Saved: {saved_attachments_count})"
                            )
                        )

            self.stdout.write(self.style.SUCCESS("Email ingestion batch completed successfully."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during email ingestion: {str(e)}"))

        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass