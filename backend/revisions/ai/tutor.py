"""AI help around the revision sheets: a self-assessment quiz and a personalised revision plan.

Both use the same path as the summaries (Gemini, then the local model) and stay grounded in data
the student can see: the quiz is written from the sheet only, the plan only orders items the
platform found (unread sheets, cards to review, missed quizzes, planned sessions).
"""
import random
import re
import unicodedata
from datetime import timedelta
from django.apps import apps
from django.utils import timezone
from rest_framework.exceptions import APIException
from .clients import AIServiceError, generate_json

QUIZ_INSTRUCTIONS = """Tu crées un quiz d'auto-évaluation pour un étudiant francophone à partir d'une fiche de révision.
Règles :
- Chaque question porte sur une notion de la fiche et se résout avec la fiche seule ; n'invente aucun fait.
- Quatre propositions distinctes et plausibles, une seule correcte ; évite « toutes les réponses » et les négations piégeuses.
- "answer" est l'indice (0 à 3) de la bonne proposition dans "choices".
- "explanation" justifie la bonne réponse en une ou deux phrases, en citant la notion de la fiche.
- Questions variées (définition, application, cause, comparaison), en français clair."""

QUIZ_SCHEMA = {
    'type': 'OBJECT',
    'properties': {'questions': {'type': 'ARRAY', 'items': {'type': 'OBJECT', 'properties': {
        'question': {'type': 'STRING'}, 'choices': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'answer': {'type': 'INTEGER'}, 'explanation': {'type': 'STRING'}},
        'required': ['question', 'choices', 'answer', 'explanation']}}},
    'required': ['questions'],
}

PLAN_INSTRUCTIONS = """Tu es un tuteur bienveillant qui aide un étudiant à organiser ses révisions du jour.
Tu reçois une liste d'éléments repérés par la plateforme, chacun avec un identifiant.
Règles :
- "advice" : deux ou trois phrases en français, encourageantes et concrètes, tutoiement, sans inventer de note ni de fait.
- "order" : les identifiants des éléments, du plus utile au moins utile aujourd'hui (uniquement des identifiants fournis).
- Ne mentionne que les informations fournies : pas de contenu de fiche, de schéma ou d'exemple supposé."""

PLAN_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'advice': {'type': 'STRING'},
        'order': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
    },
    'required': ['advice', 'order'],
}


def words(text):
    text = unicodedata.normalize('NFKD', str(text).casefold())
    return set(re.findall(r'[a-z0-9]{4,}', ''.join(c for c in text if not unicodedata.combining(c))))


def sheet_material(sheet):
    parts = [f'Fiche : {sheet.title}', f'Cours : {sheet.course_label}', sheet.summary or '']
    if sheet.key_points: parts.append('Points clés :\n' + '\n'.join(f'- {p}' for p in sheet.key_points))
    if sheet.glossary: parts.append('Glossaire :\n' + '\n'.join(f'- {g["term"]} : {g["definition"]}' for g in sheet.glossary))
    return '\n\n'.join(p for p in parts if p.strip())[:20000]


def clean_questions(raw, seed):
    """Keep well-formed questions and spread the correct answers over the four positions."""
    rng, questions, seen = random.Random(seed), [], set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict): continue
        question = ' '.join(str(item.get('question', '')).split())[:300]
        choices = [' '.join(str(c).split())[:200] for c in item.get('choices') or [] if str(c).strip()]
        answer = item.get('answer')
        if (not question or question.casefold() in seen or len(choices) != 4 or len({c.casefold() for c in choices}) != 4
                or not isinstance(answer, int) or not 0 <= answer <= 3):
            continue
        seen.add(question.casefold())
        correct = choices[answer]
        rng.shuffle(choices)
        questions.append({'question': question, 'choices': choices, 'answer': choices.index(correct),
                          'explanation': ' '.join(str(item.get('explanation', '')).split())[:500]})
    return questions


def quiz_metrics(material, questions, requested):
    vocabulary = words(material)
    grounded = [len(words(q['choices'][q['answer']]) & vocabulary) / len(words(q['choices'][q['answer']]))
                for q in questions if words(q['choices'][q['answer']])]
    answers = [0, 0, 0, 0]
    for q in questions: answers[q['answer']] += 1
    return {'requested': requested, 'valid': len(questions), 'grounding': round(sum(grounded) / len(grounded), 3) if grounded else None,
            'answers': dict(zip('ABCD', answers)), 'material_characters': len(material)}


def self_quiz(sheet, count, seed):
    material = sheet_material(sheet)
    prompt = f'Rédige exactement {count} questions à partir de cette fiche.\n\n"""\n{material}\n"""'
    data, model, fallback, duration = generate_json(QUIZ_INSTRUCTIONS, prompt, QUIZ_SCHEMA, temperature=0.4)
    questions = clean_questions(data.get('questions') if isinstance(data, dict) else None, seed)[:count]
    if len(questions) < max(1, count // 2):
        raise AIServiceError('Les questions proposées par l’IA étaient incomplètes. Relancez le quiz.')
    return questions, model, fallback, duration, quiz_metrics(material, questions, count)


# --- Personalised revision plan -------------------------------------------------------------

def _optional(app, build):
    """Other modules are optional: their absence or failure never blocks the plan."""
    if not apps.is_installed(app): return []
    try: return build()
    except Exception: return []


def plan_items(student):
    from ..models import RevisionSheet, SheetProgress
    from ..services import readable_sheets
    from ..services.learning import flashcards
    now, items = timezone.now(), []
    shared = list(readable_sheets(student).filter(status='PUBLISHED').exclude(owner=student).order_by('-published_at')[:30])
    progress = {p.sheet_id: p for p in SheetProgress.objects.filter(student=student, sheet__in=shared)}
    for sheet in shared:
        p = progress.get(sheet.pk)
        if p is None or not p.views:
            items.append({'id': f'sheet:{sheet.pk}', 'kind': 'sheet', 'title': f'Lire la fiche « {sheet.title} »', 'detail': sheet.course_label,
                          'link': f'/espace/fiches/{sheet.pk}', 'priority': 3, 'signal': 'fiche partagée non lue'})
        else:
            ids = {c['id'] for c in flashcards(sheet)}
            known, total = len([k for k in p.known if k in ids]), len(ids)
            if total and known / total < 0.6:
                items.append({'id': f'cards:{sheet.pk}', 'kind': 'cards', 'title': f'Réviser les cartes « {sheet.title} »',
                              'detail': f'{known} / {total} cartes maîtrisées', 'link': f'/espace/fiches/{sheet.pk}/reviser',
                              'priority': 2, 'signal': f'{known} cartes maîtrisées sur {total}'})

    def quizzes():
        from quizzes.models import Attempt
        found = []
        for attempt in Attempt.objects.filter(student=student, status__in=['SUBMITTED', 'EXPIRED']).order_by('-ended_at')[:10]:
            score, total = attempt.points_earned, attempt.total_points
            if score is not None and total and score / total < 0.6 and not any(i['id'] == f'quiz:{attempt.quiz_id}' for i in found):
                found.append({'id': f'quiz:{attempt.quiz_id}', 'kind': 'quiz', 'title': f'Retravailler le quiz « {attempt.quiz_title} »',
                              'detail': f'{round(100 * score / total)} % à la dernière tentative', 'link': f'/espace/quiz/{attempt.quiz_id}',
                              'priority': 3, 'signal': f'quiz réussi à {round(100 * score / total)} %'})
        return found

    def planning():
        from planning.models import RevisionTask
        today = timezone.localdate()
        tasks = RevisionTask.objects.filter(student=student, status='TODO', plan__status='ACTIVE',
                                            starts_at__date__gte=today, starts_at__date__lte=today + timedelta(days=1)).order_by('starts_at')[:5]
        return [{'id': f'task:{t.pk}', 'kind': 'task', 'title': t.title, 'detail': f'Prévu le {timezone.localtime(t.starts_at):%d/%m à %H:%M}',
                 'link': '/espace/planning', 'priority': 2, 'signal': 'tâche de révision prévue'} for t in tasks]

    items += _optional('quizzes', quizzes) + _optional('planning', planning)
    return sorted(items, key=lambda i: -i['priority'])[:8]


def rules_advice(items):
    if not items:
        return 'Tu es à jour : aucune fiche ni aucun quiz ne t’attend. Profites-en pour relire une fiche déjà vue ou avancer sur ton planning.'
    first = items[0]['title'][0].lower() + items[0]['title'][1:]
    return f'Commence par {first}. Avance ensuite dans la liste à ton rythme : chaque élément te rapproche de tes objectifs.'


def revision_plan(student):
    items = plan_items(student)
    if not items:
        return {'advice': rules_advice(items), 'items': [], 'engine': 'rules', 'model': ''}
    payload = '\n'.join(f'- {i["id"]} : {i["title"]} ({i["signal"]})' for i in items)
    try:
        data, model, fallback, duration = generate_json(PLAN_INSTRUCTIONS, f'Éléments repérés pour {student.first_name} :\n{payload}', PLAN_SCHEMA, temperature=0.5)
    except APIException:
        return {'advice': rules_advice(items), 'items': items, 'engine': 'rules', 'model': ''}
    known = {i['id']: i for i in items}
    order = [i for i in dict.fromkeys(data.get('order') or []) if i in known] if isinstance(data, dict) else []
    ordered = [known[i] for i in order] + [i for i in items if i['id'] not in order]
    advice = ' '.join(str(data.get('advice', '')).split())[:600] or rules_advice(ordered)
    return {'advice': advice, 'engine': 'ollama' if model.startswith('ollama/') else 'gemini', 'model': model, 'duration_ms': duration,
            # Each item keeps the fact that put it on the list: the model only orders and encourages.
            'items': [{**i, 'reason': i['signal']} for i in ordered]}
