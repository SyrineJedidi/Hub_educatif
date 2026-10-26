import json
import re
import time
from collections import Counter
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import NotFound
from accounts.models import User
from classrooms.models import LearningGroup
from assistant.content import providers
from assistant.indexing import ensure_index
from assistant.insights import percentile
from assistant.llm import LLMError, answer_schema, generate_answer, provider_status
from assistant.models import Mode
from assistant.prompts import build_prompt, parse_answer
from assistant.retrieval import retrieve

DATASET = Path(__file__).resolve().parents[2] / 'evaluation' / 'demo_dataset.json'


class Command(BaseCommand):
    help = ('Évalue l’assistant sur un jeu de questions : sources retrouvées (hit@5), refus hors cours, statut, latence et jetons. '
        'Utilise le fournisseur configuré (ASSISTANT_LLM_PROVIDER) ; avec Gemini, chaque question consomme une requête du quota.')

    def add_arguments(self, parser):
        parser.add_argument('--source-type', default='group', help='group ou course.')
        parser.add_argument('--scope', required=True, help='Identifiant du groupe ou du cours (un code de groupe est aussi accepté).')
        parser.add_argument('--dataset', default=str(DATASET), help='Fichier JSON ("questions": [{question, expected_source, out_of_scope}]).')
        parser.add_argument('--mode', default=Mode.EXPLICATION, choices=Mode.values)
        parser.add_argument('--min-score', type=float, default=None, help='Seuil de pertinence à tester (par défaut ASSISTANT_MIN_SCORE).')
        parser.add_argument('--retrieval-only', action='store_true', help='Mesure seulement la recherche, sans appeler le modèle.')
        parser.add_argument('--pause', type=float, default=0.0, help='Pause en secondes entre deux appels au modèle (limite par minute).')
        parser.add_argument('--json', action='store_true', help='Rapport JSON sur la sortie standard.')

    def scope(self, provider, value):
        if provider.source_type == 'group' and not re.fullmatch(r'[0-9a-fA-F]{24}', value):
            group = LearningGroup.objects.filter(code=value.strip().upper()).first()
            if not group: raise CommandError(f'Aucun groupe avec le code {value}.')
            value = str(group.pk)
        admin = User.objects.filter(role='ADMIN', is_active=True).first()
        if not admin: raise CommandError('Un compte administrateur actif est nécessaire pour lire le contenu évalué.')
        try: return provider.get_managed_scope(admin, value)
        except NotFound: raise CommandError('Contenu introuvable.')

    def handle(self, *args, **options):
        provider = providers().get(options['source_type'])
        if not provider: raise CommandError(f'Type de contenu indisponible : {options["source_type"]}.')
        scope = self.scope(provider, options['scope'])
        try: questions = json.loads(Path(options['dataset']).read_text(encoding='utf-8'))['questions']
        except (OSError, ValueError, KeyError) as exc: raise CommandError(f'Jeu de données illisible : {exc}')
        min_score = settings.ASSISTANT_MIN_SCORE if options['min_score'] is None else options['min_score']
        index = ensure_index(provider, scope.scope_id)
        results, calls = [], 0
        for item in questions:
            results.append(self.evaluate(scope, index, item, options, min_score, calls))
            calls += results[-1]['model_called']
        report = {'summary': summary(results, scope, index, options, min_score), 'results': results}
        if options['json']:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            self.stdout.write(text_report(report))

    def evaluate(self, scope, index, item, options, min_score, calls):
        question = item['question']
        started = time.monotonic()
        hits = retrieve(scope.source_type, scope.scope_id, index.content_version, question, min_score=min_score)
        retrieval_ms = int((time.monotonic() - started) * 1000)
        titles = list(dict.fromkeys(h.chunk.source_title for h in hits))
        row = {'question': question, 'expected_source': item.get('expected_source'), 'expected_out_of_scope': bool(item.get('out_of_scope')),
            'retrieved_sources': titles, 'top_score': hits[0].score if hits else None, 'retrieval_ms': retrieval_ms,
            'hit_at_1': (titles[:1] == [item['expected_source']]) if item.get('expected_source') else None,
            'hit_at_5': (item.get('expected_source') in titles) if item.get('expected_source') else None,
            'status': None, 'error_code': '', 'latency_ms': None, 'prompt_tokens': None, 'output_tokens': None,
            'citations': 0, 'unsourced': False, 'model_called': False}
        if not hits:
            row.update(status='OUT_OF_SCOPE', predicted_out_of_scope=True)
            return row
        row['predicted_out_of_scope'] = False
        if options['retrieval_only']: return row
        if calls and options['pause']: time.sleep(options['pause'])
        system, contents, used = build_prompt(scope.title, options['mode'], [], hits, question)
        row['model_called'] = True
        try:
            result = generate_answer(system, contents, answer_schema())
        except LLMError as exc:
            row.update(status='BLOCKED' if exc.code == 'blocked' else 'FAILED', error_code=exc.code, latency_ms=exc.latency_ms)
            return row
        _, citations, _, unsourced, out_of_scope = parse_answer(result.data, used)
        row.update(status='OUT_OF_SCOPE' if out_of_scope else 'COMPLETE', predicted_out_of_scope=out_of_scope, latency_ms=result.latency_ms,
            prompt_tokens=result.prompt_tokens, output_tokens=result.output_tokens, citations=len(citations), unsourced=unsourced)
        return row


def rate(part, whole):
    return round(part / whole, 3) if whole else None


def summary(results, scope, index, options, min_score):
    answerable = [r for r in results if not r['expected_out_of_scope']]
    refused = [r for r in results if r['expected_out_of_scope']]
    with_source = [r for r in answerable if r['hit_at_5'] is not None]
    latencies = [r['latency_ms'] for r in results if r['model_called'] and r['latency_ms'] is not None]
    statuses = Counter(r['status'] or 'NOT_CALLED' for r in results)
    return {
        'scope': {'source_type': scope.source_type, 'scope_id': scope.scope_id, 'title': scope.title},
        'llm': provider_status(), 'mode': options['mode'], 'min_score': min_score, 'retrieval_only': options['retrieval_only'],
        'chunks': index.chunks_count, 'questions': len(results), 'answerable': len(answerable), 'out_of_scope_expected': len(refused),
        'hit_rate_at_1': rate(sum(1 for r in with_source if r['hit_at_1']), len(with_source)),
        'hit_rate_at_5': rate(sum(1 for r in with_source if r['hit_at_5']), len(with_source)),
        'refusal_accuracy': rate(sum(1 for r in refused if r.get('predicted_out_of_scope')), len(refused)),
        'false_refusals': sum(1 for r in answerable if r.get('predicted_out_of_scope')),
        'refused_before_model': sum(1 for r in results if not r['retrieved_sources']),
        'statuses': dict(statuses), 'failures': statuses.get('FAILED', 0) + statuses.get('BLOCKED', 0),
        'model_calls': sum(1 for r in results if r['model_called']),
        'latency_ms': {'p50': percentile(latencies, 50), 'p95': percentile(latencies, 95)},
        'retrieval_ms': {'p50': percentile([r['retrieval_ms'] for r in results], 50), 'p95': percentile([r['retrieval_ms'] for r in results], 95)},
        'tokens': {'prompt': sum(r['prompt_tokens'] or 0 for r in results), 'output': sum(r['output_tokens'] or 0 for r in results)},
        'unsourced_answers': sum(1 for r in results if r['unsourced']),
    }


def text_report(report):
    s = report['summary']
    pct = lambda value: '—' if value is None else f'{value * 100:.0f} %'
    lines = [f"Évaluation de l’assistant — {s['scope']['title']} ({s['llm']['provider']} {s['llm']['model']}, seuil {s['min_score']})", '']
    for r in report['results']:
        flag = 'hors cours' if r['expected_out_of_scope'] else ('source OK' if r['hit_at_5'] else 'source manquée')
        lines.append(f"- [{r['status'] or 'NON APPELÉ'}] {r['question']} ({flag}, score {r['top_score']}, {r['latency_ms'] or r['retrieval_ms']} ms)")
    lines += ['', f"Bonne source en premier (hit@1) : {pct(s['hit_rate_at_1'])}", f"Sources retrouvées (hit@5) : {pct(s['hit_rate_at_5'])}", f"Refus hors cours corrects : {pct(s['refusal_accuracy'])}",
        f"Refus à tort : {s['false_refusals']}", f"Appels au modèle : {s['model_calls']} ; échecs : {s['failures']}",
        f"Latence p50 / p95 : {s['latency_ms']['p50']} / {s['latency_ms']['p95']} ms", f"Jetons : {s['tokens']['prompt']} en entrée, {s['tokens']['output']} en sortie"]
    return '\n'.join(lines)
