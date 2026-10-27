"""Benchmark the local question generator (Ollama) on a fixed corpus and write a measured report."""
import re
import statistics
import time
import unicodedata
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from rest_framework.exceptions import APIException
from accounts.models import User
from classrooms.models import LearningGroup
from quizzes.generation import generate_questions
from quizzes.generation_jobs import proposal_metrics
from quizzes.models import QuestionGenerationJob, Quiz

CORPUS = [
    ('Biologie', 'La photosynthèse', 'La photosynthèse permet aux plantes de convertir l’énergie lumineuse en énergie chimique. '
     'Elle se déroule dans les chloroplastes, qui contiennent la chlorophylle. La phase lumineuse a lieu dans les thylakoïdes : '
     'elle produit de l’ATP et du NADPH et libère du dioxygène par photolyse de l’eau. Le cycle de Calvin se déroule dans le stroma : '
     'l’enzyme RuBisCO y fixe le dioxyde de carbone pour produire des glucides.'),
    ('Informatique', 'Les listes en Python', 'Une liste Python est une séquence modifiable d’éléments. On la crée avec des crochets. '
     'La méthode append ajoute un élément à la fin, insert l’ajoute à une position donnée et remove supprime la première occurrence d’une valeur. '
     'La fonction len renvoie le nombre d’éléments. Les indices commencent à zéro et un indice négatif compte depuis la fin. '
     'Le découpage liste[a:b] renvoie une nouvelle liste du rang a inclus au rang b exclu.'),
    ('Histoire', 'La Révolution française', 'La Révolution française commence en 1789. Les états généraux se réunissent en mai 1789 à Versailles. '
     'Le 14 juillet 1789, la prise de la Bastille devient le symbole de la fin de l’absolutisme. '
     'En août 1789, l’Assemblée nationale constituante abolit les privilèges puis adopte la Déclaration des droits de l’homme et du citoyen. '
     'La monarchie est abolie en septembre 1792 et la Première République est proclamée.'),
]


def words(text):
    text = unicodedata.normalize('NFKD', text.casefold())
    return {w for w in re.findall(r'[a-z0-9]{4,}', ''.join(c for c in text if not unicodedata.combining(c)))}


def grounding(course, proposals):
    """Share of the significant words of each correct answer that appear in the course (1.0 = fully grounded)."""
    vocabulary, scores = words(course), []
    for p in proposals:
        answer = words(p['choice_' + p['correct_answer'].lower()])
        if answer: scores.append(len(answer & vocabulary) / len(answer))
    return statistics.mean(scores) if scores else None


def pct(value):
    return '—' if value is None else f'{round(value * 100)} %'


def sec(ms):
    return '—' if ms is None else f'{ms / 1000:.1f} s'


class Command(BaseCommand):
    help = 'Évalue la génération de questions (Ollama) sur un corpus fixe et écrit un rapport Markdown.'

    def add_arguments(self, parser):
        parser.add_argument('--teacher', default='enseignant@demo.nexora.test', help='Enseignant propriétaire du quiz de test.')
        parser.add_argument('--count', type=int, default=3, choices=range(1, 11), help='Questions demandées par cours.')
        parser.add_argument('--runs', type=int, default=1, help='Générations par cours.')
        parser.add_argument('--report', default=str(Path(settings.BASE_DIR).parent / 'docs' / 'QUIZ-IA-EVALUATION.md'))

    def handle(self, *args, teacher, count, runs, report, **options):
        owner = User.objects.filter(email=teacher, role='TEACHER', is_active=True).first()
        group = LearningGroup.objects.filter(teacher=owner, archived=False).first() if owner else None
        if not group: raise CommandError('Enseignant actif avec un groupe actif introuvable (lancez seed_demo).')
        quiz = Quiz.objects.create(title='[Évaluation] Génération IA', description='Quiz temporaire d’évaluation de la génération.',
                                   teacher=owner, learning_group=group, level='EASY', duration_minutes=10, max_attempts=1)
        rows = []
        try:
            for subject, title, text in CORPUS:
                for run in range(runs):
                    self.stdout.write(f'{title} ({run + 1}/{runs})…', ending=' ')
                    started = time.monotonic()
                    try:
                        proposals = generate_questions(quiz, {'course_text': text, 'count': count, 'level': 'EASY'})
                        error = ''
                    except APIException as exc:
                        proposals, error = [], str(exc.get_codes())
                    latency = int((time.monotonic() - started) * 1000)
                    metrics = proposal_metrics({'count': count}, proposals)
                    rows.append((subject, title, latency, error, metrics, grounding(text, proposals)))
                    self.stdout.write(f'{error or "OK"} {sec(latency)}')
        finally:
            quiz.delete()
        Path(report).write_text(self.render(rows, count), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Rapport écrit : {report}'))

    def render(self, rows, count):
        ok = [r for r in rows if not r[3]]
        latencies = sorted(r[2] for r in ok)
        answers = {}
        for r in ok:
            for letter, n in r[4]['answers'].items(): answers[letter] = answers.get(letter, 0) + n
        total = sum(answers.values())
        grounded = [r[5] for r in ok if r[5] is not None]
        lines = [
            '# Évaluation de la génération de questions (Quiz et progression)', '',
            f'Mesures du {timezone.localtime():%d/%m/%Y à %H:%M}, modèle local `{settings.OLLAMA_MODEL}` (Ollama), '
            f'{count} questions demandées par cours, corpus fixe de {len(CORPUS)} cours.',
            'Commande : `python manage.py evaluate_quiz_generation`.', '',
            '## Indicateurs', '',
            '| Indicateur | Valeur | Lecture |', '|---|---|---|',
            f'| Générations réussies | {len(ok)} / {len(rows)} ({pct(len(ok) / len(rows) if rows else None)}) | réponse complète et conforme au schéma |',
            f'| Questions valides | {sum(r[4]["returned"] for r in ok)} / {count * len(ok)} | toutes passent les validations du quiz (4 choix distincts, réponse A–D, explication, notion) |',
            f'| Énoncés distincts | {pct(sum(r[4]["distinct_statements"] for r in ok) / max(1, sum(r[4]["returned"] for r in ok)))} | absence de doublons dans une génération |',
            f'| Ancrage dans le cours | {pct(statistics.mean(grounded) if grounded else None)} | part des mots de la bonne réponse présents dans le cours (indicateur d’hallucination) |',
            f'| Répartition des bonnes réponses | {", ".join(f"{k} {pct(v / total)}" for k, v in sorted(answers.items())) or "—"} | une répartition équilibrée évite qu’on devine la réponse |',
            f'| Temps de réponse médian | {sec(statistics.median(latencies) if latencies else None)} | appel complet à Ollama |',
            f'| Temps de réponse maximal | {sec(latencies[-1] if latencies else None)} | justifie le traitement en arrière-plan |', '',
            '## Détail par cours', '',
            '| Matière | Cours | Résultat | Durée | Questions | Notions | Ancrage |', '|---|---|---|---|---|---|---|',
        ]
        for subject, title, latency, error, metrics, ground in rows:
            lines.append(f'| {subject} | {title} | {error or "réussie"} | {sec(latency)} | {metrics["returned"]} | {metrics["notions"]} | {pct(ground)} |')
        since = timezone.now() - timedelta(days=30)
        jobs = list(QuestionGenerationJob.objects.filter(created_at__gte=since, status__in=['SUCCEEDED', 'FAILED']))
        if jobs:
            done = [j for j in jobs if j.status == 'SUCCEEDED']
            lat = sorted(j.metrics.get('latency_ms', 0) for j in done)
            errors = {}
            for j in jobs:
                if j.status == 'FAILED': errors[j.error_code] = errors.get(j.error_code, 0) + 1
            lines += ['', '## Générations réelles (30 derniers jours)', '',
                      f'- {len(jobs)} générations lancées par les enseignants, {len(done)} réussies ({pct(len(done) / len(jobs))}).',
                      f'- Temps médian : {sec(statistics.median(lat) if lat else None)} ; 90e centile : {sec(lat[int(0.9 * (len(lat) - 1))] if lat else None)}.',
                      f'- Échecs par cause : {", ".join(f"{k} ({v})" for k, v in sorted(errors.items())) or "aucun"}.']
        lines += ['', '## Méthode', '',
                  '- La génération tourne en arrière-plan (Celery + Redis, ou un thread sans broker) : la requête répond 202 et la page '
                  'interroge la tâche ; aucune requête HTTP ne reste bloquée pendant l’appel au modèle.',
                  '- Chaque tâche enregistre ses mesures (durée, modèle, questions valides, répartition des réponses) sans conserver '
                  'le cours ni les propositions, effacés après lecture par l’enseignant.',
                  '- Les propositions restent relues par l’enseignant avant tout ajout au quiz.', '']
        return '\n'.join(lines)
