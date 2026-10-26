"""Jeu de données de démonstration couvrant toute l'application (base de développement uniquement)."""
import math
import secrets
from datetime import timedelta
from io import BytesIO
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from PIL import Image, ImageDraw
from accounts.models import User
from attendance.models import Attendance, AttendanceSheet, LearningSession
from classrooms.models import Enrollment, LearningGroup
from quizzes.attempt_services import create_attempt, finalize
from quizzes.models import Answer, Attempt, Question, Quiz
from revisions.services.learning import flashcards
from revisions.models import Illustration, RevisionSheet, SheetProgress
from revisions.services import normalized_image, store_image

DOMAIN = 'demo.nexora.test'
TEACHERS = [('enseignant', 'Amel', 'Ben Salah'), ('enseignant2', 'Karim', 'Haddad')]
# code, name, teacher, level, archived
GROUPS = [('BIO-L1', 'Biologie L1 — Groupe A', 'enseignant', 'L1', False),
          ('INFO-L2', 'Informatique L2 — Groupe B', 'enseignant2', 'L2', False),
          ('CHIM-2025', 'Chimie L1 — Promotion 2025', 'enseignant', 'L1', True)]
# login, first name, last name, current groups, ended groups
STUDENTS = [('etudiant', 'Yassine', 'Trabelsi', ['BIO-L1'], []),
            ('etudiante2', 'Salma', 'Gharbi', ['BIO-L1', 'INFO-L2'], []),
            ('etudiant3', 'Mehdi', 'Jlassi', ['INFO-L2'], []),
            ('etudiant.sans.groupe', 'Ines', 'Ferchichi', [], []),
            ('ancien.etudiant', 'Omar', 'Mansouri', [], ['BIO-L1'])]
# group, title, days from today, start hour, duration (h), location, status, attendance {login: status} or None
SESSIONS = [
    ('BIO-L1', 'Cours 1 — La cellule', -21, 9, 2, 'Salle B12', 'COMPLETED',
     {'etudiant': 'PRESENT', 'etudiante2': 'PRESENT', 'ancien.etudiant': 'LATE'}),
    ('BIO-L1', 'Cours 2 — La photosynthèse', -14, 9, 2, 'Salle B12', 'COMPLETED',
     {'etudiant': 'LATE', 'etudiante2': 'ABSENT', 'ancien.etudiant': 'PRESENT'}),
    ('BIO-L1', 'TD 1 — Écosystèmes', -7, 14, 2, 'Labo 3', 'COMPLETED', {'etudiant': 'PRESENT', 'etudiante2': 'EXCUSED'}),
    ('BIO-L1', 'Cours 3 — La respiration cellulaire', -1, 9, 2, 'Salle B12', 'PLANNED', None),
    ('BIO-L1', 'Sortie terrain — Parc du Belvédère', -3, 8, 4, 'Parc du Belvédère', 'CANCELLED', None),
    ('BIO-L1', 'Cours 4 — Génétique', 2, 9, 2, 'Salle B12', 'PLANNED', None),
    ('INFO-L2', 'Cours 1 — Complexité', -10, 10, 2, 'Amphi A', 'COMPLETED', {'etudiante2': 'PRESENT', 'etudiant3': 'ABSENT'}),
    ('INFO-L2', 'TP 1 — Algorithmes de tri', -3, 13, 3, 'Labo info 2', 'COMPLETED', {'etudiante2': 'PRESENT', 'etudiant3': 'PRESENT'}),
    ('INFO-L2', 'Cours 2 — Structures de données', 4, 10, 2, 'Amphi A', 'PLANNED', None),
]
Q = lambda statement, a, b, c, d, correct, explanation, points=1: dict(
    statement=statement, choice_a=a, choice_b=b, choice_c=c, choice_d=d, correct_answer=correct, explanation=explanation, points=points)
QUIZZES = [
    dict(group='BIO-L1', title='Photosynthèse — les bases', level='EASY', status='PUBLISHED', duration_minutes=10, max_attempts=2,
         description='Vérifiez vos connaissances sur la photosynthèse avant le TD.', questions=[
             Q('Où se déroule la photosynthèse ?', 'Dans la mitochondrie', 'Dans le chloroplaste', 'Dans le noyau', 'Dans le ribosome', 'B', 'Les chloroplastes contiennent la chlorophylle.'),
             Q('Quel gaz est absorbé ?', 'Le dioxygène', 'L’azote', 'Le dioxyde de carbone', 'L’hydrogène', 'C', 'Le CO₂ est fixé lors du cycle de Calvin.', 2),
             Q('Quel pigment capte la lumière ?', 'La chlorophylle', 'L’hémoglobine', 'La mélanine', 'La kératine', 'A', 'La chlorophylle absorbe le bleu et le rouge.'),
             Q('Que produit la phase claire ?', 'Du glucose seulement', 'ATP, NADPH et O₂', 'Du CO₂', 'De l’amidon', 'B', 'La phase claire fournit l’énergie au cycle de Calvin.', 2)]),
    dict(group='BIO-L1', title='La cellule eucaryote', level='MEDIUM', status='DRAFT', duration_minutes=15, max_attempts=1,
         description='Brouillon en cours de préparation.', questions=[
             Q('Quel organite contient l’ADN ?', 'Le noyau', 'Le Golgi', 'Le lysosome', 'La vacuole', 'A', 'Le noyau protège l’information génétique.'),
             Q('Où est produite l’énergie ?', 'Le noyau', 'La mitochondrie', 'Le réticulum', 'La membrane', 'B', 'La mitochondrie est le siège de la respiration.')]),
    dict(group='BIO-L1', title='Écologie — session 2025', level='HARD', status='ARCHIVED', duration_minutes=None, max_attempts=1,
         description='Ancien quiz conservé pour mémoire.', questions=[
             Q('Que regroupe un écosystème ?', 'Biotope et biocénose', 'Seulement les animaux', 'Seulement le climat', 'Les décomposeurs', 'A', 'Écosystème = milieu + êtres vivants.')]),
    dict(group='INFO-L2', title='Algorithmes de tri', level='MEDIUM', status='PUBLISHED', duration_minutes=None, max_attempts=3,
         description='Complexité et fonctionnement des tris classiques.', questions=[
             Q('Complexité du tri fusion ?', 'O(n)', 'O(n log n)', 'O(n²)', 'O(log n)', 'B', 'Le tri fusion divise puis fusionne : n log n.', 2),
             Q('Pire cas du tri rapide ?', 'O(n log n)', 'O(n)', 'O(n²)', 'O(1)', 'C', 'Un mauvais pivot dégrade en n².', 2),
             Q('Quel tri est stable ?', 'Tri rapide', 'Tri fusion', 'Tri par tas', 'Aucun', 'B', 'Le tri fusion conserve l’ordre des égaux.')]),
]
# student, quiz title, answers by position (None = sans réponse)
ATTEMPTS = [('etudiant', 'Photosynthèse — les bases', ['B', 'C', 'A', 'A']),
            ('etudiante2', 'Photosynthèse — les bases', ['B', 'C', 'A', 'B']),
            ('etudiante2', 'Algorithmes de tri', ['B', 'A', 'B']),
            ('etudiant3', 'Algorithmes de tri', ['B', 'C', None])]
PHOTO_SUMMARY = """## Définition
La **photosynthèse** permet aux végétaux chlorophylliens de convertir l’énergie lumineuse en énergie chimique. Elle se déroule dans les **chloroplastes**.

## Les deux phases
- **Phase claire** : dans les thylakoïdes, la chlorophylle capte la lumière ; l’eau est oxydée et libère du dioxygène.
- **Cycle de Calvin** : dans le stroma, le CO₂ est fixé pour produire des glucides grâce à l’ATP et au NADPH.

## Bilan
6 CO₂ + 6 H₂O + lumière → C₆H₁₂O₆ + 6 O₂."""
SHEETS = [
    dict(owner='enseignant', group='BIO-L1', title='La photosynthèse', course_label='Biologie végétale', color='TEAL', status='PUBLISHED',
         pinned=True, tags=['photosynthèse', 'énergie'], summary=PHOTO_SUMMARY, ai_generated=True, ai_reviewed=True, ai_model='gemini-3.5-flash',
         source_name='chapitre3-photosynthese.pdf', illustration_prompt='A green leaf absorbing sunlight, CO2 and water entering, oxygen leaving',
         key_points=['La photosynthèse convertit la lumière en énergie chimique.', 'Elle a lieu dans les chloroplastes.',
                     'La phase claire produit ATP, NADPH et O₂.', 'Le cycle de Calvin fixe le CO₂.'],
         glossary=[{'term': 'Chloroplaste', 'definition': 'Organite où se déroule la photosynthèse.'},
                   {'term': 'Chlorophylle', 'definition': 'Pigment vert qui absorbe la lumière.'}],
         illustrations=[('leaf', 'Une feuille capte la lumière, absorbe le CO₂ et l’eau, rejette du dioxygène.', 'AI'),
                        ('cell', 'Cellule végétale avec son noyau et ses chloroplastes.', 'UPLOAD')]),
    dict(owner='enseignant', group='BIO-L1', title='La cellule eucaryote', course_label='Biologie cellulaire', color='INDIGO', status='DRAFT',
         tags=['cellule'], ai_generated=True, ai_reviewed=False, ai_model='gemini-3.5-flash', source_name='Texte collé',
         summary='## Organisation\nLa cellule eucaryote possède un **noyau** et des organites spécialisés.\n\n- Le **noyau** contient l’ADN.\n- Les **mitochondries** produisent l’énergie.',
         key_points=['Le noyau protège l’information génétique.', 'Les mitochondries produisent l’ATP.'],
         glossary=[{'term': 'Organite', 'definition': 'Structure spécialisée délimitée par une membrane.'}],
         illustrations=[('cell', 'Vue simplifiée d’une cellule eucaryote.', 'UPLOAD')]),
    dict(owner='enseignant', group='BIO-L1', title='Les écosystèmes', course_label='Écologie', color='AMBER', status='DRAFT', tags=['écologie']),
    dict(owner='enseignant', group='BIO-L1', title='Chaînes alimentaires', course_label='Écologie', color='CORAL', status='PUBLISHED',
         tags=['écologie'], summary='## Producteurs et consommateurs\nLes **producteurs** fabriquent leur matière organique ; les **consommateurs** se nourrissent d’autres êtres vivants.',
         key_points=['L’énergie circule des producteurs vers les consommateurs.'], illustrations=[('cycle', 'Cycle de la matière.', 'UPLOAD')]),
    dict(owner='enseignant', group='BIO-L1', title='Biologie — révisions 2025', course_label='Biologie végétale', color='ROSE', status='ARCHIVED',
         tags=['archive'], summary='## Fiche de l’an dernier\nConservée pour mémoire.', key_points=['Fiche archivée en lecture seule.']),
    dict(owner='enseignant2', group='INFO-L2', title='Les algorithmes de tri', course_label='Algorithmique', color='SKY', status='PUBLISHED',
         tags=['tri', 'complexité'], summary='## Principe\nUn **algorithme de tri** range les éléments d’une liste.\n\n- **Tri fusion** : O(n log n).\n- **Tri rapide** : O(n log n) en moyenne, O(n²) au pire.',
         key_points=['Le tri fusion est stable.', 'Le tri rapide dépend du choix du pivot.'],
         glossary=[{'term': 'Complexité', 'definition': 'Coût d’un algorithme selon la taille des données.'}]),
    dict(owner='enseignant2', group='INFO-L2', title='Les structures de données', course_label='Algorithmique', color='TEAL', status='DRAFT',
         tags=['structures'], summary='## Brouillon\nPiles, files et listes chaînées : à compléter.', key_points=['Une pile suit le principe LIFO.']),
    dict(owner='etudiant', group=None, title='Mes notes — Respiration cellulaire', course_label='Biologie cellulaire', color='ROSE', status='DRAFT',
         tags=['examen'], summary='## À retenir\nLa respiration **dégrade le glucose** pour produire de l’ATP.', key_points=['Glucose + O₂ → CO₂ + H₂O + ATP.']),
]
ROLES = {'enseignant': 'Enseignant — Biologie L1 (BIO-L1) et groupe archivé CHIM-2025',
         'enseignant2': 'Enseignant — Informatique L2 (INFO-L2)',
         'etudiant': 'Étudiant — BIO-L1', 'etudiante2': 'Étudiante — BIO-L1 et INFO-L2',
         'etudiant3': 'Étudiant — INFO-L2', 'etudiant.sans.groupe': 'Étudiante — aucun groupe',
         'ancien.etudiant': 'Étudiant — inscription BIO-L1 terminée (historique seulement)'}


def art(kind):
    img = Image.new('RGB', (1200, 900), (246, 247, 254))
    d = ImageDraw.Draw(img)
    if kind == 'leaf':
        d.ellipse((880, 60, 1100, 280), fill=(255, 205, 80))
        d.polygon([(250, 700), (420, 260), (720, 200), (820, 420), (600, 720)], fill=(46, 170, 120))
        d.line([(260, 690), (760, 260)], fill=(20, 110, 80), width=10)
    elif kind == 'cell':
        d.ellipse((150, 120, 1050, 800), fill=(230, 244, 238), outline=(18, 158, 134), width=14)
        d.ellipse((480, 330, 720, 560), fill=(170, 150, 235), outline=(110, 80, 200), width=8)
        for x, y in [(330, 300), (850, 360), (360, 600), (800, 640)]:
            d.ellipse((x - 80, y - 40, x + 80, y + 40), fill=(80, 190, 140), outline=(30, 120, 90), width=6)
    else:
        pts = [(600 + 280 * math.cos(math.radians(a)), 450 + 280 * math.sin(math.radians(a))) for a in (-90, 30, 150)]
        for i, p in enumerate(pts): d.line([p, pts[(i + 1) % 3]], fill=(200, 205, 235), width=12)
        for p, c in zip(pts, [(82, 95, 225), (18, 158, 134), (239, 95, 88)]):
            d.ellipse((p[0] - 110, p[1] - 110, p[0] + 110, p[1] + 110), fill=c)
    out = BytesIO(); img.save(out, format='PNG'); return out.getvalue()


class Command(BaseCommand):
    help = 'Crée ou complète un jeu de données de démonstration pour toute l’application. Base de développement uniquement.'

    def add_arguments(self, parser):
        parser.add_argument('--password', help='Mot de passe commun des comptes de démonstration (sinon généré aléatoirement).')

    def handle(self, *args, password=None, **options):
        password = password or secrets.token_urlsafe(12)
        try: validate_password(password)
        except ValidationError as exc: raise CommandError(' '.join(exc.messages))
        self.now = timezone.now()
        users = self.accounts(password)
        groups = self.groups(users)
        counts = dict(sessions=self.sessions(users, groups), quizzes=self.quizzes(users, groups),
                      attempts=self.attempts(users), sheets=self.sheets(users, groups),
                      progress=self.progress(users))
        self.stdout.write(self.style.SUCCESS('Données de démonstration prêtes.'))
        self.stdout.write('  ' + ', '.join(f'{v} {k} créé(e)s' for k, v in counts.items()) + ' (les éléments existants sont conservés).')
        for login, purpose in [('admin', 'Administrateur — toute l’application')] + list(ROLES.items()):
            email = users['admin'].email if login == 'admin' else f'{login}@{DOMAIN}'
            self.stdout.write(f'  {email:<42} {purpose}')
        self.stdout.write(f'Mot de passe commun : {password}')

    def accounts(self, password):
        def account(login, first, last, role):
            user, _ = User.objects.get_or_create(email=f'{login}@{DOMAIN}', defaults=dict(first_name=first, last_name=last, role=role))
            user.first_name, user.last_name, user.is_active = first, last, True
            user.set_password(password); user.save()
            return user
        users = {}
        admin = User.objects.filter(role='ADMIN').first()
        if not admin: admin = account('admin', 'Admin', 'Nexora', 'ADMIN')
        elif admin.email.endswith('@' + DOMAIN): admin.set_password(password); admin.save()
        else: self.stdout.write(self.style.WARNING(f'Administrateur existant conservé sans modification : {admin.email}'))
        users['admin'] = admin
        for login, first, last in TEACHERS: users[login] = account(login, first, last, 'TEACHER')
        for login, first, last, *_ in STUDENTS: users[login] = account(login, first, last, 'STUDENT')
        return users

    def groups(self, users):
        groups = {}
        for code, name, teacher, level, archived in GROUPS:
            groups[code], _ = LearningGroup.objects.get_or_create(code=code, defaults=dict(
                name=name, teacher=users[teacher], level=level, academic_year='2025-2026' if archived else '2026-2027', archived=archived))
        for login, _, _, current, ended in STUDENTS:
            for code in current + ended:
                if not Enrollment.objects.filter(student=users[login], group=groups[code]).exists():
                    Enrollment.objects.create(student=users[login], group=groups[code], starts_at=self.now - timedelta(days=60),
                                              ends_at=self.now - timedelta(days=5) if code in ended else None)
        return groups

    def sessions(self, users, groups):
        created = 0
        for code, title, days, hour, hours, location, status, attendance in SESSIONS:
            group = groups[code]
            if LearningSession.objects.filter(group=group, title=title).exists(): continue
            start = timezone.localtime(self.now).replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days)
            session = LearningSession.objects.create(group=group, title=title, starts_at=start, ends_at=start + timedelta(hours=hours),
                location=location, status=status, creator=group.teacher, description=f'Séance de démonstration — {group.name}.')
            created += 1
            if attendance:
                entries = [Attendance(student_id=str(users[login].pk), student_name=f'{users[login].first_name} {users[login].last_name}',
                                      status=value, author_id=str(group.teacher_id), updated_at=session.ends_at,
                                      comment='Certificat médical fourni.' if value == 'EXCUSED' else '')
                           for login, value in attendance.items()]
                AttendanceSheet.objects.create(session=session, entries=entries, validated=True, version=1)
        return created

    def quizzes(self, users, groups):
        created = 0
        for data in QUIZZES:
            data = dict(data); questions = data.pop('questions'); group = groups[data.pop('group')]
            if Quiz.objects.filter(teacher=group.teacher, title=data['title']).exists(): continue
            quiz = Quiz.objects.create(teacher=group.teacher, learning_group=group,
                published_at=self.now - timedelta(days=10) if data['status'] != 'DRAFT' else None, **data)
            for position, question in enumerate(questions, 1): Question.objects.create(quiz=quiz, position=position, **question)
            created += 1
        return created

    def progress(self, users):
        """Readings and flashcard revisions, so the teacher follow-up has something to show."""
        created = 0
        # Salma has read and revised « La photosynthèse »; Mehdi only read « Les algorithmes de tri ».
        for login, title, views, known_share in [('etudiante2', 'La photosynthèse', 3, 0.8), ('etudiant3', 'Les algorithmes de tri', 1, 0)]:
            sheet = RevisionSheet.objects.filter(title=title, status='PUBLISHED').first()
            if not sheet or SheetProgress.objects.filter(sheet=sheet, student=users[login]).exists(): continue
            cards = [c['id'] for c in flashcards(sheet)]
            known = cards[:round(len(cards) * known_share)]
            SheetProgress.objects.create(sheet=sheet, student=users[login], views=views, known=known,
                first_viewed_at=self.now - timedelta(days=3), last_viewed_at=self.now - timedelta(hours=5),
                review_sessions=2 if known else 0, last_reviewed_at=self.now - timedelta(hours=5) if known else None)
            created += 1
        return created

    def attempts(self, users):
        created = 0
        for login, title, choices in ATTEMPTS:
            student, quiz = users[login], Quiz.objects.filter(title=title).first()
            if not quiz or Attempt.objects.filter(student=student, quiz=quiz).exists(): continue
            attempt = create_attempt(student, quiz, 1)
            for snapshot, choice in zip(attempt.question_snapshot, choices):
                if choice: Answer.objects.create(attempt=attempt, question_id=snapshot['id'], selected_choice=choice)
            finalize(attempt)
            created += 1
        return created

    def sheets(self, users, groups):
        created = 0
        for data in SHEETS:
            data = dict(data); owner = users[data.pop('owner')]; code = data.pop('group')
            illustrations = data.pop('illustrations', [])
            if RevisionSheet.objects.filter(owner=owner, title=data['title']).exists(): continue
            sheet = RevisionSheet.objects.create(owner=owner, learning_group=groups[code] if code else None,
                generated_at=self.now if data.get('ai_generated') else None,
                published_at=self.now if data['status'] == 'PUBLISHED' else None, **data)
            for position, (kind, caption, source) in enumerate(illustrations, 1):
                content, width, height = normalized_image(art(kind))
                Illustration.objects.create(sheet=sheet, image=store_image(content), caption=caption, source=source, width=width,
                    height=height, position=position, ai_model='black-forest-labs/FLUX.1-schnell' if source == 'AI' else '',
                    prompt=data.get('illustration_prompt', '') if source == 'AI' else '')
            created += 1
        return created
