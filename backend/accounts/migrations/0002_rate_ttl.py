from django.db import migrations

def ttl(apps,schema_editor):
    schema_editor.connection.database['accounts_ratebucket'].create_index('expires_at',expireAfterSeconds=0,name='rate_expiration')

def undo(apps,schema_editor):
    schema_editor.connection.database['accounts_ratebucket'].drop_index('rate_expiration')

class Migration(migrations.Migration):
    dependencies=[('accounts','0001_initial')]
    operations=[migrations.RunPython(ttl,undo)]
