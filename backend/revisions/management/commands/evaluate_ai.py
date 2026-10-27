"""Benchmark the AI pipeline on a fixed corpus and write a measured report (real API calls)."""
import statistics
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from accounts.models import User
from classrooms.models import LearningGroup
from revisions.ai.corpus import CORPUS, IMAGE_PROMPTS
from revisions.ai.jobs import run_job
from revisions.models import AIJob, RevisionSheet
from revisions.services import delete_sheet_files, remove_files


def pct(value):
    return '—' if value is None else f'{round(value * 100)} %'


def sec(ms):
    return '—' if ms is None else f'{ms / 1000:.1f} s'


class Command(BaseCommand):
    help = 'Évalue Gemini / Ollama / Hugging Face sur un corpus fixe et écrit un rapport Markdown.'

    def add_arguments(self, parser):
        parser.add_argument('--teacher', default='enseignant@demo.nexora.test', help='Enseignant propriétaire des fiches de test.')
        parser.add_argument('--length', default='STANDARD', choices=['SHORT', 'STANDARD', 'DETAILED'])
        parser.add_argument('--images', type=int, default=len(IMAGE_PROMPTS), help='Nombre d’illustrations à générer (0 pour aucune).')
        parser.add_argument('--report', default=str(Path(settings.BASE_DIR).parent / 'docs' / 'AI-EVALUATION.md'))
        parser.add_argument('--keep', action='store_true', help='Conserver les fiches d’évaluation créées.')

    def handle(self, *args, teacher, length, images, report, keep, **options):
        owner = User.objects.filter(email=teacher, role='TEACHER', is_active=True).first()
        group = LearningGroup.objects.filter(teacher=owner, archived=False).first() if owner else None
        if not group: raise CommandError('Enseignant actif avec un groupe actif introuvable (lancez seed_demo).')
        summaries, illustrations, sheets = [], [], []
        for subject, title, text in CORPUS:
            sheet = RevisionSheet.objects.create(owner=owner, learning_group=group, title=f'[Évaluation] {title}', course_label=subject)
            sheets.append(sheet)
            job = AIJob.objects.create(kind='SUMMARY', sheet=sheet, sheet_title=sheet.title, user=owner, source_text=text,
                source_name='Corpus d’évaluation', params={'length': length, 'course': subject, 'source_characters': len(text)})
            self.stdout.write(f'Résumé « {title} »…', ending=' ')
            run_job(job.pk); job.refresh_from_db()
            self.stdout.write(f'{job.status} {sec(job.duration_ms)} {job.engine}')
            summaries.append((subject, title, job))
        for (prompt, style, caption), sheet in zip(IMAGE_PROMPTS[:images], sheets):
            job = AIJob.objects.create(kind='ILLUSTRATION', sheet=sheet, sheet_title=sheet.title, user=owner,
                params={'prompt': prompt, 'style': style, 'caption': caption})
            self.stdout.write(f'Illustration ({style})…', ending=' ')
            run_job(job.pk); job.refresh_from_db()
            self.stdout.write(f'{job.status} {sec(job.duration_ms)}')
            illustrations.append(job)
        Path(report).write_text(self.render(summaries, illustrations, length), encoding='utf-8')
        if not keep:
            for sheet in sheets:
                names = delete_sheet_files(sheet); sheet.delete(); remove_files(names)
        self.stdout.write(self.style.SUCCESS(f'Rapport écrit : {report}'))

    def render(self, summaries, illustrations, length):
        ok = [j for _, _, j in summaries if j.status == 'SUCCEEDED']
        def mean(key):
            values = [j.metrics.get(key) for j in ok if j.metrics.get(key) is not None]
            return statistics.mean(values) if values else None
        durations = sorted(j.duration_ms for j in ok)
        images_ok = [j for j in illustrations if j.status == 'SUCCEEDED']
        image_durations = sorted(j.duration_ms for j in images_ok)
        def p(values, ratio): return values[min(len(values) - 1, round(ratio * (len(values) - 1)))] if values else None
        lines = [
            '# Évaluation de l’IA — Résumés et illustrations', '',
            f'Mesures réelles produites par `manage.py evaluate_ai` le {timezone.localtime():%d/%m/%Y à %H:%M} '
            f'(résumés « {length} », traitement des tâches identique à la production). Relancer la commande régénère ce rapport.', '',
            '## Configuration', '',
            f'- Résumés : `{settings.REVISIONS_GEMINI_MODEL if settings.GEMINI_API_KEY else "—"}` ; secours local : `{settings.REVISIONS_OLLAMA_MODEL or "aucun"}`',
            f'- Illustrations : `{settings.HF_IMAGE_SPACE or settings.HF_IMAGE_MODEL}` (Hugging Face)',
            f'- Corpus : {len(summaries)} extraits de cours ({", ".join(s for s, _, _ in summaries)}), {len(illustrations)} illustrations', '',
            '## Synthèse', '',
            '| Indicateur | Valeur |', '|---|---|',
            f'| Résumés réussis | {len(ok)} / {len(summaries)} ({pct(len(ok) / len(summaries) if summaries else None)}) |',
            f'| Recours au secours Ollama | {sum(j.fallback for j in ok)} |',
            f'| Durée de génération — médiane / p95 / max | {sec(p(durations, .5))} / {sec(p(durations, .95))} / {sec(durations[-1] if durations else None)} |',
            f'| Couverture des mots-clés (moyenne) | {pct(mean("keyword_coverage"))} |',
            f'| Taux de compression (moyenne) | {pct(mean("compression"))} |',
            f'| Conformité de structure (moyenne) | {pct(mean("structure_score"))} |',
            f'| Illustrations réussies | {len(images_ok)} / {len(illustrations)} |',
            f'| Durée illustration — médiane / max | {sec(p(image_durations, .5))} / {sec(image_durations[-1] if image_durations else None)} |', '',
            '## Détail par cours', '',
            '| Matière | Cours | Statut | Moteur | Durée | Mots source → résumé | Compression | Couverture | Structure | Points clés | Glossaire | Mots-clés manquants |',
            '|---|---|---|---|---|---|---|---|---|---|---|---|',
        ]
        for subject, title, j in summaries:
            m = j.metrics
            lines.append(f'| {subject} | {title} | {j.status} | {j.engine or "—"} | {sec(j.duration_ms)} | '
                         f'{m.get("source_words", "—")} → {m.get("summary_words", "—")} | {pct(m.get("compression"))} | '
                         f'{pct(m.get("keyword_coverage"))} | {pct(m.get("structure_score"))} | {m.get("key_points", "—")} | '
                         f'{m.get("glossary_terms", "—")} | {", ".join(m.get("keywords_missing", [])) or "—"} |')
            if j.error: lines.append(f'| | | Erreur : {j.error} | | | | | | | | | |')
        if illustrations:
            lines += ['', '## Illustrations', '', '| Style | Statut | Durée | Attente |', '|---|---|---|---|']
            lines += [f'| {j.params.get("style")} | {j.status} | {sec(j.duration_ms)} | {sec(j.queue_ms)} |' for j in illustrations]
        lines += ['', '## Méthode et lecture des indicateurs', '',
            'Un résumé génératif n’a pas de « bonne réponse » unique : précision, rappel ou F1 ne s’appliquent pas directement. '
            'La qualité est donc estimée par des indicateurs reproductibles, complétés par les signaux humains collectés dans l’application.', '',
            '- **Couverture des mots-clés** : part des 15 termes les plus fréquents du cours (hors mots outils, 5 lettres minimum) retrouvés dans le résumé, les points clés ou le glossaire, avec tolérance aux flexions (préfixe de 6 lettres). C’est un rappel des notions essentielles.',
            '- **Compression** : nombre de mots du résumé divisé par celui du cours. Une valeur inférieure à 100 % indique une vraie synthèse. Pour des extraits courts comme ce corpus, la longueur « Standard » peut s’en approcher.',
            '- **Conformité de structure** : moyenne de cinq contrôles (sections titrées, nombre de points clés attendu, glossaire présent, longueur dans la cible à ±25 %, idée d’illustration).',
            '- **Signaux humains** (tableau de bord *Pilotage IA*) : note de pertinence de 1 à 5 donnée par l’auteur, et taux de contenus relus avant publication (relecture obligatoire).',
            '- **Performance** : la requête HTTP répond en environ 0,2 s (202 Accepted) ; la génération s’exécute dans un worker Celery (Redis) ou dans la file de tâches intégrée, et l’interface suit la tâche par interrogation régulière.',
            '', 'Limites : corpus réduit (6 cours) ; les mots-clés fréquents ne capturent pas toutes les notions ; les durées dépendent de la charge des services externes au moment de la mesure.', '']
        return '\n'.join(lines)
