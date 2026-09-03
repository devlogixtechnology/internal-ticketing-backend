import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Ticket

logger = logging.getLogger(__name__)


@shared_task
def send_ticket_assigned_email(ticket_id, agent_email):
    """
    Jab ticket kisi agent ko assign ho to background email bhejny ke liye.
    """
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        subject = f"New Ticket Assigned: #{ticket.id} - {ticket.title}"
        message = (
            f"Hello,\n\n"
            f"You have been assigned to Ticket #{ticket.id}.\n\n"
            f"Title: {ticket.title}\n"
            f"Priority: {ticket.priority}\n"
            f"Category: {ticket.category.name if ticket.category else 'N/A'}\n\n"
            f"Please check the ticketing dashboard for details."
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@yourdomain.com'),
            recipient_list=[agent_email],
            fail_silently=False,
        )
        logger.info(f"Email sent successfully for Ticket #{ticket.id} to {agent_email}")
        return f"Email sent to {agent_email}"
    except Ticket.DoesNotExist:
        logger.error(f"Ticket #{ticket_id} not found for assignment notification")
        return f"Ticket #{ticket_id} not found"
    except Exception as e:
        logger.error(f"Failed to send assignment email for Ticket #{ticket_id}: {str(e)}")
        raise e


@shared_task
def send_status_update_email(ticket_id, new_status):
    """
    Jab ticket ka status update ho to creator ko background email bhejny ke liye.
    """
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        if not ticket.created_by.email:
            return f"User {ticket.created_by.username} has no email address."

        subject = f"Ticket #{ticket.id} Status Updated to {new_status}"
        message = (
            f"Hi {ticket.created_by.username},\n\n"
            f"Your ticket '{ticket.title}' status has been updated to: {new_status}.\n\n"
            f"Regards,\nInternal Ticketing Support"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@yourdomain.com'),
            recipient_list=[ticket.created_by.email],
            fail_silently=False,
        )
        logger.info(f"Status update email sent for Ticket #{ticket.id}")
        return f"Status update email sent for Ticket #{ticket.id}"
    except Ticket.DoesNotExist:
        logger.error(f"Ticket #{ticket_id} not found for status update notification")
        return f"Ticket #{ticket_id} not found"
    except Exception as e:
        logger.error(f"Failed to send status update email for Ticket #{ticket_id}: {str(e)}")
        raise e


@shared_task
def auto_close_resolved_tickets(days=7):
    """
    Periodic task: Jo tickets Resolved hain aur X din se inactive hain unko auto-close karne ke liye.
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    resolved_tickets = Ticket.objects.filter(status='RESOLVED', updated_at__lte=cutoff_date)
    
    count = resolved_tickets.count()
    resolved_tickets.update(status='CLOSED', updated_at=timezone.now())
    
    logger.info(f"Auto-closed {count} resolved tickets inactive for {days} days.")
    return f"Auto-closed {count} tickets."