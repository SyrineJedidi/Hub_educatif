"""Complete demo data for every account and every module, created through the API like a real user.

Runs ``seed_demo`` (accounts, groups, sessions, quizzes, sheets), removes leftovers of automated
checks, then adds what the other modules need to be explored: more students, courses with PDF
resources, quiz attempts with varied scores, sheets of the IT group, course notes for the assistant
and revision plans. Idempotent: an element that already exists is kept. Development base only.
"""
import re
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from classrooms.models import Enrollment, LearningGroup

DOMAIN = 'demo.nexora.test'
# login, first name, last name, groups
MORE_STUDENTS = [('etudiant4', 'Rania', 'Ben Ali', ['BIO-L1']), ('etudiant5', 'Ahmed', 'Karray', ['BIO-L1', 'INFO-L2']),
                 ('etudiant6', 'Nour', 'Mejri', ['INFO-L2']), ('etudiant7', 'Youssef', 'Chaabane', ['BIO-L1'])]
COURSES = [
    dict(teacher='enseignant', group='BIO-L1', subject=('Biologie', 'BIO', 'Sciences du vivant : cellule, métabolisme, écologie.'),
         title='Biologie cellulaire et végétale', description='Organisation de la cellule et grandes fonctions des végétaux.', chapters=[
             ('La cellule eucaryote', 'cellule.pdf', ['La cellule eucaryote', 'Toute cellule eucaryote possède un noyau qui contient l’ADN.',
              'Les mitochondries assurent la respiration cellulaire et produisent l’ATP.',
              'Le réticulum endoplasmique et l’appareil de Golgi fabriquent et transportent les protéines.',
              'Les cellules végétales possèdent en plus une paroi, une vacuole et des chloroplastes.']),
             ('La photosynthèse', 'photosynthese.pdf', ['La photosynthèse', 'Elle se déroule dans les chloroplastes, qui contiennent la chlorophylle.',
              'La phase lumineuse, dans les thylakoïdes, produit de l’ATP et du NADPH et libère du dioxygène.',
              'Le cycle de Calvin, dans le stroma, fixe le dioxyde de carbone grâce à l’enzyme RuBisCO.',
              'Le glucose produit stocke l’énergie lumineuse sous forme chimique.'])]),
    dict(teacher='enseignant2', group='INFO-L2', subject=('Informatique', 'INFO', 'Algorithmique, structures de données et programmation.'),
         title='Algorithmique et structures de données', description='Complexité, tris et structures de données classiques.', chapters=[
             ('La complexité', 'complexite.pdf', ['La complexité des algorithmes', 'La complexité mesure le nombre d’opérations en fonction de la taille n des données.',
              'On note O(n) une complexité linéaire et O(n²) une complexité quadratique.',
              'La recherche dichotomique dans un tableau trié est en O(log n).']),
             ('Les algorithmes de tri', 'tris.pdf', ['Les algorithmes de tri', 'Le tri fusion divise le tableau, trie chaque moitié puis fusionne : O(n log n).',
              'Le tri rapide choisit un pivot ; son pire cas est en O(n²).',
              'Un tri est stable s’il conserve l’ordre des éléments égaux, comme le tri fusion.'])]),
]
INFO_SHEETS = [
    dict(title='Les algorithmes de tri', course_label='Algorithmique', tags=['tri', 'complexité'],
         summary='## Principe\nUn algorithme de tri range les éléments d’une liste dans un ordre donné.\n\n## Tris classiques\n- **Tri fusion** : diviser, trier, fusionner ; O(n log n), stable.\n- **Tri rapide** : partition autour d’un pivot ; O(n log n) en moyenne, O(n²) au pire.\n- **Tri par insertion** : efficace sur de petites listes presque triées.',
         key_points=['Le tri fusion est en O(n log n) et stable.', 'Le pire cas du tri rapide est en O(n²).', 'Le tri par insertion convient aux petites listes presque triées.'],
         glossary=[{'term': 'Stabilité', 'definition': 'Propriété d’un tri qui conserve l’ordre des éléments égaux.'},
                   {'term': 'Pivot', 'definition': 'Élément autour duquel le tri rapide partitionne la liste.'}]),
    dict(title='La complexité algorithmique', course_label='Algorithmique', tags=['complexité'],
         summary='## Définition\nLa complexité estime le nombre d’opérations d’un algorithme selon la taille n des données.\n\n## Ordres de grandeur\n- O(1) : constant\n- O(log n) : logarithmique, comme la recherche dichotomique\n- O(n) : linéaire\n- O(n²) : quadratique, comme deux boucles imbriquées',
         key_points=['La recherche dichotomique est en O(log n).', 'Deux boucles imbriquées donnent souvent du O(n²).'],
         glossary=[{'term': 'Notation O', 'definition': 'Borne supérieure de la croissance du nombre d’opérations.'}]),
]
NOTES = {'BIO-L1': [('La cellule eucaryote — notes de cours', 'Le noyau contient l’ADN. Les mitochondries produisent l’ATP par la respiration cellulaire. Les cellules végétales ont une paroi, une vacuole et des chloroplastes.'),
                    ('La photosynthèse — notes de cours', 'La photosynthèse se déroule dans les chloroplastes. La phase lumineuse a lieu dans les thylakoïdes et libère du dioxygène. Le cycle de Calvin, dans le stroma, fixe le dioxyde de carbone grâce à la RuBisCO.')],
         'INFO-L2': [('Complexité — notes de cours', 'La complexité mesure le nombre d’opérations selon la taille n. La recherche dichotomique est en O(log n). Deux boucles imbriquées donnent O(n²).'),
                     ('Tris — notes de cours', 'Le tri fusion est en O(n log n) et stable. Le tri rapide est en O(n log n) en moyenne et O(n²) au pire.')]}
# student, quiz, answers ; scores vary so that statistics and the revision plan have something to show
ATTEMPTS = [('etudiant4', 'Photosynthèse — les bases', ['B', 'C', 'A', 'B']), ('etudiant5', 'Photosynthèse — les bases', ['A', 'A', 'B', 'C']),
            ('etudiant7', 'Photosynthèse — les bases', ['B', 'A', 'A', 'B']), ('etudiant5', 'Algorithmes de tri', ['B', 'C', 'B']),
            ('etudiant6', 'Algorithmes de tri', ['A', 'C', 'A']), ('etudiant3', 'Algorithmes de tri', ['B', 'A', 'A']),
            ('etudiante2', 'Complexité algorithmique', ['B', 'C', 'A']), ('etudiant3', 'Complexité algorithmique', ['B', 'A', 'B']),
            ('etudiant6', 'Complexité algorithmique', ['A', 'C', 'A']), ('etudiant5', 'Complexité algorithmique', ['B', 'C', 'C'])]
# Second published quiz of the IT group, created by its teacher through the API.
INFO_QUIZ = dict(title='Complexité algorithmique', description='Ordres de grandeur et coût des algorithmes classiques.', level='MEDIUM',
                 duration_minutes=10, max_attempts=2, questions=[
    ('Complexité de la recherche dichotomique ?', 'O(n)', 'O(log n)', 'O(n²)', 'O(1)', 'B', 'On divise l’intervalle par deux à chaque étape.'),
    ('Deux boucles imbriquées sur n éléments donnent souvent…', 'O(n)', 'O(log n)', 'O(n²)', 'O(2ⁿ)', 'C', 'n tours de boucle, chacun de n tours.'),
    ('Accès à un élément d’un tableau par son indice ?', 'O(1)', 'O(n)', 'O(log n)', 'O(n log n)', 'A', 'L’adresse se calcule directement.')])
# Accounts without a current group still have their own space: personal sheets and a personal plan.
PERSONAL_SHEETS = [('etudiant.sans.groupe', 'Mes notes — méthodes de révision', 'Méthodologie',
                    '## Bien réviser\n- Relire ses notes le jour même.\n- Espacer les révisions : J+1, J+3, J+7.\n- Se tester plutôt que relire.',
                    ['Le rappel actif fixe mieux que la relecture.', 'Espacer les révisions améliore la mémorisation.']),
                   ('ancien.etudiant', 'Mes notes — la cellule', 'Biologie',
                    '## La cellule\nUnité de base du vivant. Le noyau contient l’ADN ; les mitochondries produisent l’ATP.',
                    ['Le noyau contient l’ADN.', 'Les mitochondries produisent l’énergie de la cellule.'])]
PLANS = [('etudiant', 'BIO-L1', 'Réussir l’examen de biologie', 'Examen de biologie végétale'),
         ('etudiante2', 'INFO-L2', 'Maîtriser les algorithmes de tri', 'Partiel d’algorithmique'),
         ('etudiant5', 'BIO-L1', 'Revoir la photosynthèse', 'Contrôle de biologie'),
         ('etudiant3', 'INFO-L2', 'Comprendre la complexité', 'Partiel d’algorithmique'),
         ('etudiant4', 'BIO-L1', 'Préparer le contrôle sur la cellule', 'Contrôle de biologie'),
         ('etudiant6', 'INFO-L2', 'Réviser les tris', 'Partiel d’algorithmique'),
         ('etudiant7', 'BIO-L1', 'Rattraper le cours sur la photosynthèse', 'Examen de biologie végétale'),
         ('etudiant.sans.groupe', None, 'Prendre de bonnes habitudes de révision', 'Bilan personnel'),
         ('ancien.etudiant', None, 'Revoir les bases de biologie', 'Remise à niveau')]
CLEANUP_TITLES = r'^(Test e2e|IA en arrière-plan|\[Évaluation\])'


class Command(BaseCommand):
    help = 'Données de démonstration complètes pour tous les comptes et tous les modules (base de développement).'

    def add_arguments(self, parser):
        parser.add_argument('--password', required=True, help='Mot de passe commun des comptes de démonstration.')

    def handle(self, *args, password, **options):
        call_command('seed_demo', password=password, stdout=self.stdout)
        self.now, self.report = timezone.now(), []
        self.cleanup()
        users = {u.email.split('@')[0]: u for u in User.objects.filter(email__endswith='@' + DOMAIN)}
        groups = {g.code: g for g in LearningGroup.objects.all()}
        users.update(self.students(password, groups))
        self.courses(users, groups)
        self.sheets(users, groups)
        self.info_quiz(users, groups)
        self.attempts(users)
        self.notes(users, groups)
        self.personal_sheets(users)
        self.plans(users, groups)
        self.stdout.write(self.style.SUCCESS('Données complètes prêtes :'))
        for line in self.report: self.stdout.write('  ' + line)

    def client(self, user):
        client = APIClient(HTTP_HOST='127.0.0.1')
        client.force_login(user)
        return client

    def call(self, client, method, path, data=None, expected=(200, 201, 202), **kwargs):
        response = getattr(client, method)('/api/' + path, data, **({'format': 'json'} | kwargs))
        if response.status_code not in expected:
            self.stdout.write(self.style.WARNING(f'  {method.upper()} {path} → {response.status_code} {str(getattr(response, "data", ""))[:160]}'))
            return None
        return response.data

    def cleanup(self):
        """Leftovers of the automated end-to-end checks."""
        from quizzes.models import Answer, Attempt, Quiz, QuestionGenerationJob
        from revisions.models import AIJob, RevisionSheet
        removed = 0
        for quiz in Quiz.objects.filter(title__regex=CLEANUP_TITLES):
            # MongoDB deletes without subqueries: explicit lists of identifiers.
            ids = list(Attempt.objects.filter(quiz=quiz).values_list('pk', flat=True))
            Answer.objects.filter(attempt_id__in=ids).delete(); Attempt.objects.filter(pk__in=ids).delete()
            QuestionGenerationJob.objects.filter(quiz=quiz).delete()
            quiz.feedback.all().delete(); quiz.delete(); removed += 1
        for sheet in RevisionSheet.objects.filter(title__regex=CLEANUP_TITLES):
            AIJob.objects.filter(sheet=sheet).update(sheet=None); sheet.delete(); removed += 1
        try:
            from courses import models as c
            courses = list(c.Course.objects.filter(title__regex=r'^Photosynthèse BIO\d+$').values_list('pk', flat=True))
            resources = list(c.Resource.objects.filter(course_id__in=courses).values_list('pk', flat=True))
            # Protected relations are removed first, from the leaves up to the course.
            for model, field, ids in [(c.ProcessingJob, 'resource_id__in', resources), (c.ResourceSegment, 'course_id__in', courses),
                                      (c.Resource, 'pk__in', resources), (c.Chapter, 'course_id__in', courses),
                                      (c.CourseGroup, 'course_id__in', courses), (c.Course, 'pk__in', courses)]:
                model.objects.filter(**{field: ids}).delete()
            removed += len(courses)
            Subject = c.Subject
            removed += Subject.objects.filter(code__regex=r'^BIO\d{5}$').delete()[0] and 1
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'  nettoyage des cours incomplet : {exc}'))
        try:
            from assistant.models import TeacherNote
            evalia = LearningGroup.objects.filter(code='EVALIA').values_list('pk', flat=True)
            removed += TeacherNote.objects.filter(group_id__in=list(evalia)).delete()[0] and 1
            duplicates = list(TeacherNote.objects.filter(title='Photosynthèse — notes de cours').order_by('created_at').values_list('pk', flat=True))[1:]
            TeacherNote.objects.filter(pk__in=duplicates).delete()
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'  nettoyage de l’assistant incomplet : {exc}'))
        try:
            from planning.models import Deadline, RevisionTask, StudyGoal, StudyPlan
            goals = list(StudyGoal.objects.filter(title__regex=r'^Maîtriser la photosynthèse \d+$').values_list('pk', flat=True))
            plans = list(set(RevisionTask.objects.filter(goal_id__in=goals).values_list('plan_id', flat=True)))
            RevisionTask.objects.filter(plan_id__in=plans).delete(); StudyPlan.objects.filter(pk__in=plans).delete()
            deadlines = list(Deadline.objects.filter(goal_id__in=goals).values_list('pk', flat=True))
            RevisionTask.objects.filter(deadline_id__in=deadlines).delete(); Deadline.objects.filter(pk__in=deadlines).delete()
            removed += StudyGoal.objects.filter(pk__in=goals).delete()[0] and 1
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'  nettoyage du planning incomplet : {exc}'))
        group = LearningGroup.objects.filter(code='EVALIA').first()
        if group and not Enrollment.objects.filter(group=group).exists():
            try: group.delete()
            except Exception: pass
        for user in User.objects.filter(email__endswith='@exemple.test'):
            try: user.delete()
            except Exception: User.objects.filter(pk=user.pk).update(is_active=False)
        self.report.append(f'nettoyage des données de test automatiques : {removed} élément(s)')

    def students(self, password, groups):
        created, users = 0, {}
        for login, first, last, codes in MORE_STUDENTS:
            user = User.objects.filter(email=f'{login}@{DOMAIN}').first()
            if not user:
                user = User.objects.create_user(f'{login}@{DOMAIN}', password, first_name=first, last_name=last, email_verified=True); created += 1
            for code in codes:
                if not Enrollment.objects.filter(student=user, group=groups[code], ends_at__isnull=True).exists():
                    Enrollment.objects.create(student=user, group=groups[code], starts_at=self.now - timedelta(days=30))
            users[login] = user
        self.report.append(f'{created} étudiant(s) ajouté(s) ({len(MORE_STUDENTS)} au total en plus des comptes de base)')
        return users

    def pdf(self, lines):
        from fpdf import FPDF
        pdf = FPDF(); pdf.add_page()
        pdf.add_font('Noto', '', str(Path(settings.BASE_DIR) / 'quizzes' / 'fonts' / 'NotoSans.ttf'))
        pdf.set_font('Noto', size=16); pdf.multi_cell(0, 10, lines[0]); pdf.ln(4); pdf.set_font('Noto', size=12)
        for line in lines[1:]: pdf.multi_cell(0, 8, line); pdf.ln(2)
        return bytes(pdf.output())

    def courses(self, users, groups):
        from courses.models import Course, Subject
        from django.core.files.uploadedfile import SimpleUploadedFile
        admin, created = self.client(users['admin']), 0
        for spec in COURSES:
            name, code, description = spec['subject']
            subject = Subject.objects.filter(code=code).first()
            subject_id = str(subject.pk) if subject else (self.call(admin, 'post', 'subjects/', dict(name=name, code=code, description=description)) or {}).get('id')
            if not subject_id or Course.objects.filter(title=spec['title']).exists(): continue
            teacher = self.client(users[spec['teacher']])
            course = self.call(teacher, 'post', 'courses/', dict(title=spec['title'], description=spec['description'], subject_id=subject_id,
                                                                 group_ids=[str(groups[spec['group']].pk)]))
            if not course: continue
            for title, filename, lines in spec['chapters']:
                chapter = self.call(teacher, 'post', f'courses/{course["id"]}/chapters/', dict(title=title))
                if chapter:
                    self.call(teacher, 'post', f'courses/{course["id"]}/resources/', dict(chapter_id=chapter['id'], title=f'Support — {title}',
                              file=SimpleUploadedFile(filename, self.pdf(lines), content_type='application/pdf')), format='multipart')
            self.call(teacher, 'post', f'courses/{course["id"]}/publish/', {})
            created += 1
        self.report.append(f'{created} cours publié(s) avec chapitres et supports PDF (texte extrait, recherche plein texte)')

    def sheets(self, users, groups):
        from revisions.models import RevisionSheet, SheetProgress
        created = 0
        for data in INFO_SHEETS:
            if RevisionSheet.objects.filter(title=data['title']).exists(): continue
            RevisionSheet.objects.create(owner=users['enseignant2'], learning_group=groups['INFO-L2'], status='PUBLISHED', color='INDIGO',
                                         published_at=self.now - timedelta(days=2), **data)
            created += 1
        photo = RevisionSheet.objects.filter(title='La photosynthèse', status='PUBLISHED').first()
        if photo:
            for login, views in [('etudiant4', 3), ('etudiant7', 1)]:
                SheetProgress.objects.get_or_create(sheet=photo, student=users[login], defaults=dict(views=views, first_viewed_at=self.now - timedelta(days=3),
                                                    last_viewed_at=self.now - timedelta(days=1)))
        self.report.append(f'{created} fiche(s) de révision ajoutée(s) pour le groupe Informatique, progression de lecture pour 2 étudiants')

    def info_quiz(self, users, groups):
        from quizzes.models import Quiz
        if Quiz.objects.filter(title=INFO_QUIZ['title']).exists(): return
        teacher = self.client(users['enseignant2'])
        quiz = self.call(teacher, 'post', 'quizzes/', dict(title=INFO_QUIZ['title'], description=INFO_QUIZ['description'], level=INFO_QUIZ['level'],
                         learning_group_id=str(groups['INFO-L2'].pk), duration_minutes=INFO_QUIZ['duration_minutes'], max_attempts=INFO_QUIZ['max_attempts']))
        if not quiz: return
        for statement, a, b, c, d, correct, explanation in INFO_QUIZ['questions']:
            self.call(teacher, 'post', f'quizzes/{quiz["id"]}/questions/', dict(statement=statement, choice_a=a, choice_b=b, choice_c=c, choice_d=d,
                      correct_answer=correct, explanation=explanation, points=1, notion='Complexité'))
        self.call(teacher, 'post', f'quizzes/{quiz["id"]}/publish/', {})
        self.report.append('1 quiz publié pour le groupe Informatique (Complexité algorithmique)')

    def personal_sheets(self, users):
        from revisions.models import RevisionSheet
        made = 0
        for login, title, course, summary, points in PERSONAL_SHEETS:
            if RevisionSheet.objects.filter(owner=users[login], title=title).exists(): continue
            if self.call(self.client(users[login]), 'post', 'sheets/', dict(title=title, course_label=course, summary=summary, key_points=points)): made += 1
        self.report.append(f'{made} fiche(s) personnelle(s) pour les comptes sans groupe en cours')

    def attempts(self, users):
        from quizzes.models import Attempt, Quiz
        done = 0
        for login, title, answers in ATTEMPTS:
            quiz = Quiz.objects.filter(title=title, status='PUBLISHED').first()
            if not quiz or Attempt.objects.filter(quiz=quiz, student=users[login]).exists(): continue
            client = self.client(users[login])
            attempt = self.call(client, 'post', f'student/quizzes/{quiz.pk}/attempts/', {})
            if not attempt: continue
            revisions = {}
            for question, answer in zip(sorted(attempt['questions'], key=lambda q: q['position']), answers):
                saved = self.call(client, 'put', f'student/attempts/{attempt["id"]}/answers/{question["id"]}/', dict(selected_choice=answer, expected_revision=0))
                if saved: revisions[question['id']] = saved.get('revision', 1)
            if self.call(client, 'post', f'student/attempts/{attempt["id"]}/submit/', dict(answer_revisions=revisions)): done += 1
        self.report.append(f'{done} tentative(s) de quiz soumise(s) avec des scores variés')

    def notes(self, users, groups):
        from assistant.models import TeacherNote
        created = 0
        for code, notes in NOTES.items():
            teacher = self.client(groups[code].teacher)
            for title, body in notes:
                if TeacherNote.objects.filter(group=groups[code], title=title).exists(): continue
                if self.call(teacher, 'post', 'assistant/notes/', dict(group_id=str(groups[code].pk), title=title, body=body)): created += 1
        self.report.append(f'{created} note(s) de cours pour l’assistant pédagogique')

    def plans(self, users, groups):
        from planning.models import StudyGoal
        made = 0
        day = lambda n: (timezone.localdate() + timedelta(days=n)).isoformat()
        for login, code, goal_title, exam in PLANS:
            student = self.client(users[login])
            if StudyGoal.objects.filter(student=users[login], title=goal_title).exists(): continue
            goal = self.call(student, 'post', 'student/planning/goals/', dict(title=goal_title, description='Objectif créé pour la démonstration.',
                             learning_group_id=str(groups[code].pk) if code else None, target_date=day(12), priority='HIGH', estimated_hours=8))
            if not goal: continue
            self.call(student, 'post', 'student/planning/deadlines/', dict(title=exam, kind='EXAM', due_at=day(14) + 'T08:00:00Z', goal_id=goal['id']))
            for weekday, start, end in [(0, '18:00', '20:00'), (2, '18:00', '20:00'), (5, '10:00', '12:00'), (6, '14:00', '16:00')]:
                self.call(student, 'post', 'student/planning/availability/', dict(weekday=weekday, start_time=start, end_time=end), expected=(200, 201, 400))
            # Rules mode: the demo data never depends on an AI quota; Gemini stays available for live use.
            plan = self.call(student, 'post', 'student/planning/plans/generate/', dict(title=f'Plan — {goal_title}', start_date=day(0), end_date=day(13), mode='rules'))
            if plan and self.call(student, 'post', f'student/planning/plans/{plan["id"]}/activate/', {}): made += 1
        self.report.append(f'{made} planning(s) de révision actif(s) avec objectifs, échéances et disponibilités')
