import os
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.db import models
from apps.accounts.models import CustomUser


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Ticket(models.Model):
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'

    class ApprovalStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='tickets')
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    approval_status = models.CharField(
        max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )

    # Client-Scoping Foreign Key (BE2 Requirement)
    client = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='client_tickets'
    )

    created_by = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='created_tickets'
    )
    assigned_to = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_tickets'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.id} - {self.title}"

    def can_transition_to(self, user, new_status):
        if user.role == 'ADMIN' or user.is_superuser:
            return True

        # Support Team Workflow: OPEN -> IN_PROGRESS -> RESOLVED
        if user.role == 'SUPPORT' and self.assigned_to == user:
            allowed = {
                self.Status.OPEN: [self.Status.IN_PROGRESS],
                self.Status.IN_PROGRESS: [self.Status.RESOLVED],
            }
            return new_status in allowed.get(self.status, [])

        # Employee Workflow: RESOLVED -> CLOSED 
        if user.role == 'EMPLOYEE' and self.created_by == user:
            if self.status == self.Status.RESOLVED and new_status == self.Status.CLOSED:
                return True

        return False


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    comment = models.TextField()
    is_internal = models.BooleanField(default=False)  # Support/Admin internal notes
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author} on Ticket #{self.ticket_id}"


class TicketHistory(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='history')
    changed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    old_status = models.CharField(max_length=15)
    new_status = models.CharField(max_length=15)
    remarks = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Ticket Histories"

    def __str__(self):
        return f"Ticket #{self.ticket_id}: {self.old_status} → {self.new_status}"


# _______________file handling________________________

def validate_file_size(value):
    max_size_mb = 5
    if value.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"File size cannot exceed {max_size_mb}MB.")


class TicketAttachment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(
        upload_to='ticket_attachments/%Y/%m/',
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'pdf', 'txt', 'log']),
            validate_file_size,
        ]
    )
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='uploaded_attachments')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Attachment for Ticket #{self.ticket_id} - {self.filename}"

    @property
    def filename(self):
        return os.path.basename(self.file.name)


class ServerHealthLog(models.Model):
    cpu_usage = models.FloatField(help_text="CPU Usage Percentage")
    memory_usage = models.FloatField(help_text="Memory/RAM Usage Percentage")
    disk_usage = models.FloatField(help_text="Disk Space Usage Percentage")
    system_uptime = models.CharField(max_length=100, default="N/A", help_text="Server Uptime")
    active_connections = models.IntegerField(default=0, help_text="Active network/DB connections")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Server Health Log"
        verbose_name_plural = "Server Health Logs"

    def __str__(self):
        return f"Health Log ({self.timestamp.strftime('%Y-%m-%d %H:%M')}) - CPU: {self.cpu_usage}%"