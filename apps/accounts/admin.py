from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Department, CustomUser


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'department', 'phone_number', 'is_staff')
    list_filter = ('role', 'department', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'phone_number')

    fieldsets = UserAdmin.fieldsets + (
        ('Ticketing Info', {'fields': ('role', 'department', 'phone_number')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Ticketing Info', {'fields': ('role', 'department', 'phone_number')}),
    )