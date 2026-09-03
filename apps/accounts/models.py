from django.contrib.auth.models import AbstractUser
from django.db import models


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

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.EMPLOYEE
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"