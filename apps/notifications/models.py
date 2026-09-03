from django.db import models
from apps.accounts.models import CustomUser


class Notification(models.Model):
    recipient = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{'Read' if self.is_read else 'Unread'}] {self.title} → {self.recipient.username}"