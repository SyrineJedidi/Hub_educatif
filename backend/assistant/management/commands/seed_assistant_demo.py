import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from classrooms.models import LearningGroup
from assistant.models import TeacherNote

DATASET = Path(__file__).resolve().parents[2] / 'evaluation' / 'demo_dataset.json'


class Command(BaseCommand):
    help = 'Crée (ou met à jour) les notes de cours de démonstration de l’assistant pour un groupe.'

    def add_arguments(self, parser):
        parser.add_argument('--group', required=True, help='Code du groupe, par exemple PY-L1.')
        parser.add_argument('--dataset', default=str(DATASET), help='Fichier JSON contenant les notes ("notes": [{title, body}]).')

    def handle(self, *args, **options):
        group = LearningGroup.objects.filter(code=options['group'].strip().upper()).first()
        if not group: raise CommandError(f'Aucun groupe avec le code {options["group"]}.')
        if group.archived: raise CommandError(f'Le groupe {group.code} est archivé.')
        try:
            notes = json.loads(Path(options['dataset']).read_text(encoding='utf-8'))['notes']
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError(f'Jeu de données illisible : {exc}')
        created = updated = 0
        for item in notes:
            note = TeacherNote.objects.filter(group=group, title=item['title']).first()
            if not note:
                TeacherNote.objects.create(group=group, teacher=group.teacher, title=item['title'], body=item['body']); created += 1
            elif note.body != item['body'] or note.teacher_id != group.teacher_id:
                note.body, note.teacher, note.version = item['body'], group.teacher, note.version + 1
                note.save(); updated += 1
        self.stdout.write(f'Groupe {group.code} : {created} note(s) créée(s), {updated} mise(s) à jour, {len(notes) - created - updated} inchangée(s).')
        self.stdout.write(f'Évaluation : python manage.py evaluate_assistant --source-type group --scope {group.pk} --json')
