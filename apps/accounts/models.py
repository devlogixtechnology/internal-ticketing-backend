from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets
import hashlib
from datetime import timedelta
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        EMPLOYEE = 'EMPLOYEE', 'Employee'
        SUPPORT = 'SUPPORT', 'Support'
        ADMIN = 'ADMIN', 'Admin'

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    
    # FIX: choices=Role.choices aur default set kar diya gaya hai
    role = models.CharField(
        max_length=20, 
        choices=Role.choices, 
        default=Role.SUPPORT
    )
    
    # Task ke requirement ke mutabiq Client FK yahan majood hai
    client = models.ForeignKey(
        'clients.Client',  # App name 'clients' aur model 'Client'
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class APIKey(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='api_keys')
    prefix = models.CharField(max_length=8)
    hashed_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    @classmethod
    def generate_key(cls, user):
        raw_key = f"sk_{secrets.token_urlsafe(32)}"
        prefix = raw_key[:8]
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

        api_key_obj = cls.objects.create(
            user=user,
            prefix=prefix,
            hashed_key=hashed_key
        )
        return api_key_obj, raw_key


class MagicLinkToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='magic_tokens')
    token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        expiration_time = self.created_at + timedelta(minutes=15)
        return not self.is_used and timezone.now() <= expiration_time