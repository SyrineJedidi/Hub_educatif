from django.db import migrations

COLLECTIONS = ['assistant_conversation', 'assistant_message', 'assistant_answerfeedback']


def ttl(apps, schema_editor):
    # Documents without a purge date are never expired; trashed ones go 30 days after deletion.
    for name in COLLECTIONS:
        schema_editor.connection.database[name].create_index('purge_at', expireAfterSeconds=0, name='purge_expiration')


def undo(apps, schema_editor):
    for name in COLLECTIONS:
        schema_editor.connection.database[name].drop_index('purge_expiration')


class Migration(migrations.Migration):
    dependencies = [('assistant', '0001_initial')]
    operations = [migrations.RunPython(ttl, undo)]
