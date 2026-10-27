import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.db import DatabaseError, connections
from django.test import SimpleTestCase
from assistant import indexing
from assistant.content import NotesProvider, Segment
from assistant.indexing import CHUNK_SIZE, INDEX_FORMAT, OVERLAP, build_chunks, ensure_index, overlap_tail, paragraphs, word_slices
from assistant.models import KnowledgeChunk, ScopeIndex, TeacherNote
from .base import AssistantTestCase, resource_url

WORDS = 'la norme d’un vecteur mesure sa longueur et se calcule avec les coordonnées dans un repère orthonormé'.split()


def prose(length, offset=0):
    """Course-like text of about length characters, made of whole words."""
    words, size, index = [], 0, offset
    while size < length:
        words.append(WORDS[index % len(WORDS)]); size += len(words[-1]) + 1; index += 1
    return ' '.join(words)[:length].rsplit(' ', 1)[0] + '.'


def note_segment(text, chapter='Définition', page=None, start_seconds=None, url='', source_id='a' * 24, kind='NOTE', title='Les vecteurs'):
    return Segment(kind, source_id, title, chapter, page, start_seconds, url, text)


class ChunkingTests(SimpleTestCase):
    def test_slices_never_cut_inside_a_word(self):
        text = prose(5000)
        slices = word_slices(text, 300)
        self.assertEqual(' '.join(slices), text)
        self.assertTrue(all(len(s) <= 300 for s in slices))
        self.assertTrue(all(not s.startswith(' ') and not s.endswith(' ') for s in slices))
        # Only a word longer than a whole chunk has to be cut.
        self.assertEqual([len(s) for s in word_slices('a' * 2500 + ' b', 1200)], [1200, 1200, 102])

    def test_paragraphs_split_on_blank_lines_and_collapse_spaces(self):
        text = 'Premier  paragraphe\navec   deux lignes.\r\n\r\n\n   \n\nSecond.\t\n\n' + prose(3000)
        pieces = list(paragraphs(text))
        self.assertEqual(pieces[:2], ['Premier paragraphe\navec deux lignes.', 'Second.'])
        self.assertTrue(all(len(p) <= CHUNK_SIZE for p in pieces))
        self.assertEqual(' '.join(pieces[2:]), prose(3000))
        self.assertEqual(list(paragraphs('')), []); self.assertEqual(list(paragraphs(None)), [])

    def test_overlap_starts_on_a_word(self):
        text = prose(700)
        tail = overlap_tail(text)
        self.assertTrue(0 < len(tail) <= OVERLAP)
        self.assertTrue(text.endswith(tail))
        self.assertTrue(text[-len(tail) - 1].isspace())
        self.assertEqual(overlap_tail(prose(OVERLAP)), '')
        self.assertEqual(overlap_tail('a' * 300 + ' ' + 'b' * OVERLAP), 'b' * OVERLAP)
        # A single word longer than the overlap is not repeated at all.
        self.assertEqual(overlap_tail('a' * 500), '')

    def test_chunks_are_packed_with_an_overlap(self):
        segments = [note_segment(prose(450, offset=n)) for n in range(6)]
        chunks = build_chunks('group', 'b' * 24, segments)
        self.assertEqual([c.order for c in chunks], list(range(1, len(chunks) + 1)))
        self.assertGreater(len(chunks), 1)
        for previous, chunk in zip(chunks, chunks[1:]):
            self.assertTrue(chunk.text.startswith(overlap_tail(previous.text)))
        self.assertTrue(all(len(c.text) <= CHUNK_SIZE + OVERLAP + 2 for c in chunks))
        # Every paragraph is indexed: none is lost between two chunks.
        for segment in segments: self.assertTrue(any(segment.text in c.text for c in chunks))

    def test_a_chunk_never_mixes_two_sources_chapters_or_pages(self):
        segments = [note_segment('Une phrase.', chapter='A'), note_segment('Une autre.', chapter='B'), note_segment('Page trois.', page=3, chapter='B'),
            note_segment('Page quatre.', page=4, chapter='B'), note_segment('Autre note.', chapter='B', page=4, source_id='c' * 24)]
        chunks = build_chunks('group', 'b' * 24, segments)
        self.assertEqual([(c.text, c.chapter_title, c.page, c.source_id) for c in chunks], [('Une phrase.', 'A', None, 'a' * 24),
            ('Une autre.', 'B', None, 'a' * 24), ('Page trois.', 'B', 3, 'a' * 24), ('Page quatre.', 'B', 4, 'a' * 24), ('Autre note.', 'B', 4, 'c' * 24)])
        self.assertEqual(chunks[0].search_text, 'vecteur phrase')

    def test_chunk_keeps_metadata_within_field_sizes(self):
        long_title = 'T' * 250
        (chunk,) = build_chunks('course', 'b' * 24, [Segment('RESOURCE', 'r' * 24, long_title, 'C' * 250, 2, None, '/u?page=2', 'Le texte de la page.')])
        self.assertEqual((chunk.source_type, chunk.scope_id, chunk.source_kind, chunk.source_id, len(chunk.source_title), len(chunk.chapter_title), chunk.page, chunk.url),
            ('course', 'b' * 24, 'RESOURCE', 'r' * 24, 200, 200, 2, '/u?page=2'))
        huge = build_chunks('group', 'b' * 24, [note_segment('x' * 5000)])
        self.assertTrue(all(len(c.text) <= 2000 for c in huge))

    def test_number_of_chunks_is_capped(self):
        segments = [note_segment(f'Paragraphe {n}.', chapter=str(n)) for n in range(10)]
        with patch.object(indexing, 'MAX_CHUNKS', 3):
            self.assertEqual([c.chapter_title for c in build_chunks('group', 'b' * 24, segments)], ['0', '1', '2'])

    def test_a_recording_chunk_links_to_its_own_moment(self):
        course, resource = 'c' * 24, 'r' * 24
        segments = [Segment('RESOURCE', resource, 'Vidéo', 'Mesures', None, 30.0 * n, resource_url(course, resource, start_seconds=30.0 * n),
            prose(300, offset=n)) for n in range(8)]
        chunks = build_chunks('course', course, segments)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].start_seconds, 0.0)
        for chunk in chunks:
            with self.subTest(order=chunk.order):
                self.assertEqual(chunk.url, resource_url(course, resource, start_seconds=chunk.start_seconds))
        self.assertEqual(len({c.url for c in chunks}), len(chunks))


class IndexTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.provider = NotesProvider()
        self.scope_id = str(self.group.pk)

    def chunks(self):
        return list(KnowledgeChunk.objects.filter(source_type='group', scope_id=self.scope_id).order_by('order'))

    def test_first_question_builds_the_index(self):
        index = ensure_index(self.provider, self.scope_id)
        self.assertEqual(index.content_version, f'{INDEX_FORMAT}:{self.provider.version(self.scope_id)}')
        self.assertEqual((index.source_type, index.scope_id, index.chunks_count), ('group', self.scope_id, 3))
        self.assertIsNotNone(index.built_at); self.assertIsNotNone(index.build_ms)
        self.assertEqual([c.chapter_title for c in self.chunks()], ['Définition', 'Addition', 'Colinéarité'])
        self.assertFalse(KnowledgeChunk.objects.filter(scope_id=str(self.other_group.pk)).exists())

    def test_unchanged_content_is_not_rebuilt(self):
        index = ensure_index(self.provider, self.scope_id)
        ids = [c.pk for c in self.chunks()]
        with patch('assistant.indexing.build_chunks', side_effect=AssertionError('rebuilt')):
            self.assertEqual(ensure_index(self.provider, self.scope_id).pk, index.pk)
        self.assertEqual([c.pk for c in self.chunks()], ids)

    def test_changed_content_replaces_every_chunk(self):
        index = ensure_index(self.provider, self.scope_id)
        ids = {c.pk for c in self.chunks()}
        response = self.teacher_client.patch(f'/api/assistant/notes/{self.note.pk}/', {'body': '## Norme\nLa norme se calcule avec le théorème de Pythagore.'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        rebuilt = ensure_index(self.provider, self.scope_id)
        self.assertEqual(rebuilt.pk, index.pk); self.assertNotEqual(rebuilt.content_version, index.content_version)
        self.assertEqual(rebuilt.chunks_count, 1); self.assertGreaterEqual(rebuilt.built_at, index.built_at)
        chunks = self.chunks()
        self.assertEqual([c.text for c in chunks], ['La norme se calcule avec le théorème de Pythagore.'])
        self.assertFalse(ids & {c.pk for c in chunks})
        self.assertEqual(ScopeIndex.objects.filter(source_type='group', scope_id=self.scope_id).count(), 1)

    def test_a_new_chunking_format_rebuilds_existing_indexes(self):
        index = ensure_index(self.provider, self.scope_id)
        following = str(int(INDEX_FORMAT) + 1)
        with patch.object(indexing, 'INDEX_FORMAT', following):
            rebuilt = ensure_index(self.provider, self.scope_id)
        self.assertEqual(rebuilt.content_version, f'{following}:{self.provider.version(self.scope_id)}')
        self.assertNotEqual(rebuilt.content_version, index.content_version)

    def test_empty_scope_has_an_empty_index(self):
        TeacherNote.objects.filter(group=self.group).delete()
        index = ensure_index(self.provider, self.scope_id)
        self.assertEqual((index.chunks_count, self.chunks()), (0, []))

    def test_concurrent_rebuilds_write_one_set_of_chunks(self):
        # Both requests have read the missing index and built their chunks before either one writes.
        barrier, real = threading.Barrier(2, timeout=20), indexing.build_chunks
        def built(*args):
            chunks = real(*args); barrier.wait(); return chunks
        def rebuild(_):
            try: return ensure_index(NotesProvider(), self.scope_id).content_version
            finally: connections.close_all()
        with patch('assistant.indexing.build_chunks', built), ThreadPoolExecutor(max_workers=2) as pool:
            versions = list(pool.map(rebuild, range(2)))
        self.assertEqual(len(set(versions)), 1)
        self.assertEqual(ScopeIndex.objects.filter(source_type='group', scope_id=self.scope_id).count(), 1)
        self.assertEqual([c.order for c in self.chunks()], [1, 2, 3])

    def test_a_rebuild_finished_meanwhile_is_kept(self):
        ensure_index(self.provider, self.scope_id)
        TeacherNote.objects.filter(pk=self.note.pk).update(version=2, body='Une norme est une longueur.')
        provider, segments = NotesProvider(), NotesProvider().segments
        def while_reading(scope_id):
            # Another request rebuilds the same index while this one still reads the content.
            ensure_index(NotesProvider(), scope_id)
            yield from segments(scope_id)
        with patch.object(provider, 'segments', while_reading), self.assertLogs('assistant', 'INFO') as logs:
            index = ensure_index(provider, self.scope_id)
        ids = [c.pk for c in self.chunks()]
        self.assertEqual(len([line for line in logs.output if 'index rebuilt' in line]), 1)
        self.assertEqual((index.content_version, len(ids)), (f'{INDEX_FORMAT}:{self.provider.version(self.scope_id)}', 1))
        self.assertEqual(ensure_index(self.provider, self.scope_id).pk, index.pk); self.assertEqual([c.pk for c in self.chunks()], ids)

    def test_write_conflicts_are_retried_then_the_committed_index_answers(self):
        stale = ensure_index(self.provider, self.scope_id)
        TeacherNote.objects.filter(pk=self.note.pk).update(version=2, body='Une norme est une longueur.')
        real, calls = KnowledgeChunk.objects.bulk_create, []
        def flaky(chunks, *args, **kwargs):
            calls.append(len(chunks))
            if len(calls) < 3: raise DatabaseError('WriteConflict')
            return real(chunks, *args, **kwargs)
        # Two conflicts, each followed by a growing pause, then the write succeeds.
        with patch.object(KnowledgeChunk.objects, 'bulk_create', flaky), patch.object(indexing.time, 'sleep') as sleep:
            index = ensure_index(self.provider, self.scope_id)
        self.assertEqual((calls, [c.text for c in self.chunks()]), ([1, 1, 1], ['Une norme est une longueur.']))
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [0.05, 0.1])
        self.assertEqual(index.content_version, ScopeIndex.objects.get(pk=index.pk).content_version)
        TeacherNote.objects.filter(pk=self.note.pk).update(version=3, body='Encore une autre version.')
        ids = [c.pk for c in self.chunks()]
        # A write that keeps failing does not fail the question: once the wait is over, the last committed index answers it.
        with patch.object(KnowledgeChunk.objects, 'bulk_create', side_effect=DatabaseError('WriteConflict')), patch.object(indexing, 'REBUILD_WAIT_SECONDS', 0.3), \
                self.assertLogs('assistant', 'WARNING') as logs:
            postponed = ensure_index(self.provider, self.scope_id)
        self.assertEqual((postponed.pk, postponed.content_version), (index.pk, index.content_version))
        self.assertIn('assistant index rebuild postponed', logs.output[-1])
        # Each failed attempt rolled back: the previous index is intact, and the next question rebuilds it.
        self.assertEqual(ScopeIndex.objects.get(pk=index.pk).content_version, index.content_version)
        self.assertEqual([c.pk for c in self.chunks()], ids)
        self.assertNotEqual(index.content_version, stale.content_version)
        self.assertEqual((ensure_index(self.provider, self.scope_id).chunks_count, [c.text for c in self.chunks()]), (1, ['Encore une autre version.']))

    def test_a_request_that_loses_the_rebuild_waits_for_the_winner(self):
        ensure_index(self.provider, self.scope_id)
        TeacherNote.objects.filter(pk=self.note.pk).update(version=2, body='Une norme est une longueur.')
        # Both requests have built their chunks before either writes, and the first to write keeps its transaction open a moment.
        barrier, build, create = threading.Barrier(2, timeout=20), indexing.build_chunks, KnowledgeChunk.objects.bulk_create
        def built(*args):
            chunks = build(*args); barrier.wait(); return chunks
        def slow(chunks, *args, **kwargs):
            time.sleep(0.5); return create(chunks, *args, **kwargs)
        def rebuild(_):
            try: return ensure_index(NotesProvider(), self.scope_id).content_version
            finally: connections.close_all()
        with patch('assistant.indexing.build_chunks', built), patch.object(KnowledgeChunk.objects, 'bulk_create', slow), ThreadPoolExecutor(max_workers=2) as pool:
            versions = list(pool.map(rebuild, range(2)))
        self.assertEqual(versions, [f'{INDEX_FORMAT}:{self.provider.version(self.scope_id)}'] * 2)
        self.assertEqual([c.text for c in self.chunks()], ['Une norme est une longueur.'])
