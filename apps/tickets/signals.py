from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Ticket, TicketHistory
from apps.notifications.models import Notification
from apps.accounts.models import CustomUser
from .models import Ticket
from .tasks import send_ticket_assigned_email


@receiver(post_save, sender=Ticket)
def notify_on_ticket_creation(sender, instance, created, **kwargs):
    """Naya ticket banne par sabhi ADMIN users ko notification bhejo."""
    if created:
        admins = CustomUser.objects.filter(role='ADMIN')
        notifications = [
            Notification(
                recipient=admin,
                title="New Ticket Created",
                message=f"Ticket #{instance.id} '{instance.title}' created by {instance.created_by.username}."
            )
            for admin in admins
        ]
        Notification.objects.bulk_create(notifications)


@receiver(post_save, sender=TicketHistory)
def notify_on_status_change(sender, instance, created, **kwargs):
    """Ticket ka status change hone par ticket creator ko notification bhejo."""
    if created:
        ticket = instance.ticket
        recipients = set()

        # Ticket banane wale ko batayen
        if ticket.created_by:
            recipients.add(ticket.created_by)

        # Agar assigned support agent hai, usko bhi batayen (jab tak wahi change karne wala na ho)
        if ticket.assigned_to and ticket.assigned_to != instance.changed_by:
            recipients.add(ticket.assigned_to)

        for user in recipients:
            Notification.objects.create(
                recipient=user,
                title=f"Ticket #{ticket.id} Status Updated",
                message=f"Status changed from {instance.old_status} to {instance.new_status}."
                        + (f" Remarks: {instance.remarks}" if instance.remarks else "")
            )


@receiver(post_save, sender=Ticket)
def trigger_ticket_tasks(sender, instance, created, **kwargs):
    if not created and instance.assigned_to:
        # Save ke baad background task run karein
        send_ticket_assigned_email.delay(instance.id, instance.assigned_to.email)