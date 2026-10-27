from django.db import migrations


def verify_existing(apps, schema_editor):
    # Accounts created before the confirmation email existed keep their access.
    apps.get_model('accounts', 'User').objects.filter(email_verified=False).update(email_verified=True)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0005_user_unique_admin_account')]
    operations = [migrations.RunPython(verify_existing, migrations.RunPython.noop)]
