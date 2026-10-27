import os
import signal
import socket
import time
from django.core.management.base import BaseCommand
from courses.processing import claim, recover_stale, run


class Command(BaseCommand):
    help = 'Traiter les ressources de cours en attente : extraction du texte des PDF et transcription audio.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Traiter les tâches disponibles puis quitter.')
        parser.add_argument('--sleep', type=float, default=5, help='Attente en secondes quand la file est vide.')
        parser.add_argument('--limit', type=int, default=0, help='Nombre maximal de tâches (0 : sans limite).')

    def handle(self, *args, **options):
        self.stopping = False
        def stop(signum, frame): self.stopping = True
        previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
        worker = f'{socket.gethostname()}-{os.getpid()}'
        processed = 0
        try:
            while not self.stopping and not (options['limit'] and processed >= options['limit']):
                recover_stale()
                job = claim(worker=worker)
                if job is None:
                    if options['once']: break
                    # Short naps keep SIGINT and SIGTERM responsive.
                    deadline = time.monotonic() + options['sleep']
                    while not self.stopping and time.monotonic() < deadline: time.sleep(0.2)
                    continue
                processed += 1
                done = run(job)
                if done is None: outcome = 'ressource supprimée pendant le traitement'
                elif done.status == 'DONE': outcome = f'{done.get_status_display()}, {done.segments_count} segment(s), {done.processing_ms} ms'
                else: outcome = f'{done.get_status_display()} — {done.error}'
                self.stdout.write(f'{job.pk} {job.get_kind_display()} (tentative {job.attempts}) : {outcome}')
        finally:
            for sig, handler in previous.items(): signal.signal(sig, handler)
        self.stdout.write(f'{processed} tâche(s) traitée(s).')
