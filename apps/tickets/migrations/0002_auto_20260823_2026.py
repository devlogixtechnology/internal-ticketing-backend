from django.db import migrations

def add_default_categories(apps, schema_editor):
    
    Category = apps.get_model('tickets', 'Category')  
    
    default_categories = [
        'Hardware',
        'Software',
        'Network & Internet',
        'Account Access',
        'Email / Communication',
        'General Inquiry'
    ]
    
    for cat_name in default_categories:
        Category.objects.get_or_create(name=cat_name)

def remove_default_categories(apps, schema_editor):
    Category = apps.get_model('tickets', 'Category')
    Category.objects.filter(name__in=[
        'Hardware', 'Software', 'Network & Internet',
        'Account Access', 'Email / Communication', 'General Inquiry'
    ]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0001_initial'),  # Apni pichli migration file ka naam likhein
    ]

    operations = [
        migrations.RunPython(add_default_categories, reverse_code=remove_default_categories),
    ]