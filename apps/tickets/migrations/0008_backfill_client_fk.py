from django.db import migrations

def backfill_client_fk(apps, schema_editor):
    Ticket = apps.get_model('tickets', 'Ticket')
    for ticket in Ticket.objects.filter(client__isnull=True):
        if ticket.created_by:
            ticket.client = ticket.created_by
            ticket.save(update_fields=['client'])

class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0007_ticket_client'),
    ]

    operations = [
        migrations.RunPython(backfill_client_fk),
    ]