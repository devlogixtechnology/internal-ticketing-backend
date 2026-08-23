from django.db import migrations

def add_default_departments(apps, schema_editor):
    Department = apps.get_model('apps.accounts', 'Department') 
    
    default_departments = [
        'IT Support',
        'Human Resources',
        'Finance',
        'Software Engineering',
        'Operations',
        'Administration'
    ]
    
    for dept_name in default_departments:
        Department.objects.get_or_create(name=dept_name)

def remove_default_departments(apps, schema_editor):
    Department = apps.get_model('accounts', 'Department')
    Department.objects.filter(name__in=[
        'IT Support', 'Human Resources', 'Finance', 
        'Software Engineering', 'Operations', 'Administration'
    ]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),  # Apni pichli migration file ka naam yahan likhein
    ]

    operations = [
        migrations.RunPython(add_default_departments, reverse_code=remove_default_departments),
    ]