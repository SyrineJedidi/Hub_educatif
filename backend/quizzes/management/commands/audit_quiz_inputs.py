import json
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from quizzes.models import Quiz, Question


class Command(BaseCommand):
    help = 'Signaler les anciennes données Quiz–Question non conformes, sans les modifier.'

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', dest='as_json')

    def handle(self, *args, **options):
        issues = []
        fields = {
            Quiz: ('title', 'description', 'level', 'duration_minutes', 'max_attempts'),
            Question: ('statement', 'choice_a', 'choice_b', 'choice_c', 'choice_d', 'correct_answer', 'explanation', 'points', 'position'),
        }
        for model, names in fields.items():
            for instance in model.objects.all():
                errors = {}
                for name in names:
                    try: model._meta.get_field(name).clean(getattr(instance, name), instance)
                    except ValidationError as exc: errors[name] = exc.messages
                try: instance.clean()
                except ValidationError as exc: errors.update({key:value for key,value in exc.message_dict.items() if key in names})
                if errors:
                    issues.append({'entity': model.__name__, 'id': str(instance.pk),
                        'quiz_id': str(instance.pk if model is Quiz else instance.quiz_id), 'fields': errors})
        report = {'nonconforming_records': len(issues), 'modified_records': 0, 'issues': issues}
        if options['as_json']: self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(f'{len(issues)} enregistrement(s) non conforme(s). Aucune donnée modifiée.')
            for issue in issues:
                self.stdout.write(f'{issue["entity"]} {issue["id"]} : ' + '; '.join(f'{field}: {" ".join(messages)}' for field,messages in issue['fields'].items()))
