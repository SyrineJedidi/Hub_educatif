import math
from collections import Counter
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from assistant import retrieval
from assistant.content import NotesProvider
from assistant.indexing import ensure_index
from assistant.models import KnowledgeChunk, TeacherNote, ValidatedAnswer
from assistant.retrieval import Corpus, bm25, normalize, query_terms, retrieve, search_text, tokenize
from .base import IN_SCOPE, OUT_OF_SCOPE, AssistantTestCase


def corpus(*documents):
    """A corpus written by hand: (kind, search text) pairs."""
    frequencies = [Counter(text.split()) for _, text in documents]
    lengths = [sum(c.values()) for c in frequencies]
    frequency = Counter(term for counts in frequencies for term in counts)
    return Corpus(list(range(len(documents))), [kind for kind, _ in documents], frequencies, lengths, frequency, sum(lengths) / len(lengths))


class TokenizerTests(SimpleTestCase):
    def test_accents_case_and_ligatures_are_ignored(self):
        self.assertEqual(normalize('ÉNERGIE Cinétique, cœur, Ærodynamique'), 'energie cinetique, coeur, aerodynamique')
        self.assertEqual(tokenize('L’ÉNERGIE CINÉTIQUE'), tokenize('l’energie cinetique'))
        self.assertEqual(tokenize('Les Probabilités : événements CONTRAIRES et l’œuvre, pourquoi ? 2x+1'),
            ['probabilite', 'evenement', 'contraire', 'oeuvre', '2x'])

    def test_french_and_english_stop_words_and_short_tokens_are_dropped(self):
        self.assertEqual(tokenize('Qu’est-ce que la norme d’un vecteur ?'), ['norme', 'vecteur'])
        self.assertEqual(tokenize('What is the derivative of a function?'), ['derivative', 'function'])
        self.assertEqual(tokenize('Et pourquoi donc ? a b c'), [])
        self.assertEqual(tokenize('x2 vaut 3.14'), ['x2', 'vaut', '14'])

    def test_light_plural_folding(self):
        self.assertEqual(tokenize('fonctions vecteurs travaux'), tokenize('fonction vecteur travau'))
        # Short words keep their final letter: « gaz », « prix », « sens ».
        self.assertEqual(tokenize('gaz prix sens'), ['gaz', 'prix', 'sens'])

    def test_search_text_joins_title_chapter_and_body(self):
        self.assertEqual(search_text('Les vecteurs', 'Définition', 'La norme est une longueur.'), 'vecteur definition norme longueur')
        self.assertEqual(search_text('Titre', None, ''), 'titre')

    def test_previous_question_counts_half(self):
        self.assertEqual(query_terms('Et pourquoi ?', 'Comment calculer la norme d’un vecteur ?'), {'calculer': 0.5, 'norme': 0.5, 'vecteur': 0.5})
        self.assertEqual(query_terms('La norme ?', 'La norme d’un vecteur'), {'norme': 1.0, 'vecteur': 0.5})
        self.assertEqual(query_terms('La norme ?'), {'norme': 1.0})


class Bm25Tests(SimpleTestCase):
    def test_okapi_score_with_a_floor_on_the_document_count(self):
        documents = corpus(('NOTE', 'norme vecteur longueur'), ('NOTE', 'vecteur somme'))
        scores = dict((index, score) for score, index in bm25(documents, {'norme': 1.0}))
        # Twenty documents at least: one short note must not give every term an idf close to zero.
        idf = math.log(1 + (20 - 1 + 0.5) / (1 + 0.5))
        self.assertEqual(list(scores), [0])
        self.assertAlmostEqual(scores[0], idf * 1 * 2.5 / (1 + 1.5 * (0.25 + 0.75 * 3 / 2.5)))
        both = dict((index, score) for score, index in bm25(documents, {'vecteur': 1.0, 'somme': 0.5}))
        idf_vector, idf_sum = math.log(1 + 18.5 / 2.5), math.log(1 + 19.5 / 1.5)
        self.assertAlmostEqual(both[1], idf_vector * 2.5 / (1 + 1.5 * (0.25 + 0.75 * 2 / 2.5)) + 0.5 * idf_sum * 2.5 / (1 + 1.5 * (0.25 + 0.75 * 2 / 2.5)))
        self.assertGreater(both[1], both[0])

    def test_with_many_documents_the_real_count_is_used(self):
        documents = corpus(*[('NOTE', 'norme')] + [('NOTE', f'mot{i}') for i in range(29)])
        (score, index), = bm25(documents, {'norme': 1.0})
        self.assertEqual(index, 0)
        self.assertAlmostEqual(score, math.log(1 + 29.5 / 1.5) * 2.5 / (1 + 1.5))

    def test_validated_answers_weigh_half_more(self):
        documents = corpus(('NOTE', 'norme vecteur'), ('VALIDATED', 'norme vecteur'))
        scores = dict((index, score) for score, index in bm25(documents, {'norme': 1.0}))
        self.assertAlmostEqual(scores[1], scores[0] * 1.5)

    def test_unknown_terms_and_empty_corpus_score_nothing(self):
        self.assertEqual(bm25(corpus(('NOTE', 'norme')), {'capitale': 1.0}), [])
        self.assertEqual(bm25(corpus(('NOTE', 'norme')), {}), [])
        self.assertEqual(bm25(Corpus([], [], [], [], Counter(), 0.0), {'norme': 1.0}), [])


class RetrievalTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.provider = NotesProvider()
        self.scope_id = str(self.group.pk)

    def search(self, question, previous='', **options):
        index = ensure_index(self.provider, self.scope_id)
        return retrieve('group', self.scope_id, index.content_version, question, previous, **options)

    def test_best_chunks_first_with_their_score(self):
        hits = self.search(IN_SCOPE)
        self.assertEqual([h.chunk.chapter_title for h in hits], ['Définition', 'Addition', 'Colinéarité'])
        self.assertEqual([h.score for h in hits], sorted((h.score for h in hits), reverse=True))
        self.assertTrue(all(h.score == round(h.score, 4) for h in hits))
        self.assertGreater(hits[0].score, 2 * hits[1].score)

    def test_out_of_scope_and_threshold(self):
        self.assertEqual(self.search(OUT_OF_SCOPE), [])
        self.assertEqual(self.search('Et pourquoi donc ?'), [])
        top = self.search(IN_SCOPE)[0].score
        self.assertEqual([h.chunk.chapter_title for h in self.search(IN_SCOPE, min_score=top - 0.001)], ['Définition'])
        self.assertEqual(self.search(IN_SCOPE, min_score=top + 0.001), [])
        with override_settings(ASSISTANT_MIN_SCORE=top + 0.001): self.assertEqual(self.search(IN_SCOPE), [])

    def test_question_without_accents_or_in_capitals_finds_the_same_chunk(self):
        for question in ('QU’EST-CE QUE LA NORME D’UN VECTEUR ?', 'qu est ce que la norme d un vecteur', 'normes des vecteurs'):
            with self.subTest(question=question): self.assertEqual(self.search(question)[0].chunk.chapter_title, 'Définition')

    def test_follow_up_borrows_the_previous_question(self):
        self.assertEqual(self.search('Et pourquoi ?'), [])
        hits = self.search('Et pourquoi ?', IN_SCOPE)
        self.assertEqual(hits[0].chunk.chapter_title, 'Définition')
        self.assertAlmostEqual(hits[0].score, self.search(IN_SCOPE)[0].score / 2, places=3)
        # The current question still decides when it has terms of its own.
        self.assertEqual(self.search('Et la relation de Chasles ?', IN_SCOPE)[0].chunk.chapter_title, 'Addition')

    def test_at_most_five_chunks(self):
        for number in range(4):
            TeacherNote.objects.create(group=self.group, teacher=self.teacher, title=f'Exercices {number}', body=f'Calculer la norme du vecteur numéro {number}.')
        self.assertEqual(len(self.search(IN_SCOPE)), 5)
        self.assertEqual(len(self.search(IN_SCOPE, top_k=2)), 2)

    def test_validated_answer_comes_first(self):
        ValidatedAnswer.objects.create(source_type='group', scope_id=self.scope_id, question='Qu’est-ce que la norme d’un vecteur ?',
            answer='La norme est la longueur du vecteur, notée avec deux barres.', teacher=self.teacher)
        hits = self.search(IN_SCOPE)
        self.assertEqual((hits[0].chunk.source_kind, hits[1].chunk.chapter_title), ('VALIDATED', 'Définition'))

    def test_corpus_is_cached_per_content_version_and_stale_chunks_are_skipped(self):
        index = ensure_index(self.provider, self.scope_id)
        self.search(IN_SCOPE)
        self.assertIn(('group', self.scope_id, index.content_version), retrieval._cache)
        KnowledgeChunk.objects.filter(source_type='group', scope_id=self.scope_id, chapter_title='Définition').delete()
        # The cached corpus still ranks the deleted chunk first; it is dropped instead of failing.
        self.assertEqual([h.chunk.chapter_title for h in retrieve('group', self.scope_id, index.content_version, IN_SCOPE)], ['Addition', 'Colinéarité'])
        retrieval.forget('group', self.scope_id)
        self.assertNotIn(('group', self.scope_id, index.content_version), retrieval._cache)
        self.assertEqual([h.chunk.chapter_title for h in retrieve('group', self.scope_id, index.content_version, IN_SCOPE)], ['Addition', 'Colinéarité'])

    def test_a_content_version_that_comes_back_uses_the_rebuilt_chunks(self):
        expected = [h.chunk.chapter_title for h in self.search(IN_SCOPE)]
        draft = TeacherNote.objects.create(group=self.group, teacher=self.teacher, title='Brouillon', body='Une note retirée aussitôt.')
        self.assertEqual([h.chunk.chapter_title for h in self.search(IN_SCOPE)], expected)
        draft.delete()
        # Same notes as at first, hence the same version, but the rebuild gave every chunk a new id.
        self.assertEqual([h.chunk.chapter_title for h in self.search(IN_SCOPE)], expected)

    def test_cache_keeps_the_most_recent_scopes(self):
        with patch.object(retrieval, 'CACHE_SIZE', 2):
            for version in ('a', 'b', 'c'): retrieval.load_corpus('group', self.scope_id, version)
            self.assertEqual([key[2] for key in retrieval._cache], ['b', 'c'])
            retrieval.load_corpus('group', self.scope_id, 'b')
            self.assertEqual([key[2] for key in retrieval._cache], ['c', 'b'])
