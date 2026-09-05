# apps/tickets/apps.py
from django.apps import AppConfig


class TicketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tickets'

    def ready(self):
        # Signals ko HAMESHA ready() method ke andar import karein
        import apps.tickets.signals  # noqa