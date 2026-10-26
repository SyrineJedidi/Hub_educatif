import math
import re
import threading
import unicodedata
from collections import Counter, OrderedDict
from dataclasses import dataclass
from django.conf import settings
from .models import KnowledgeChunk

K1 = 1.5
B = 0.75
TOP_K = 5
VALIDATED_BOOST = 1.5
FOLLOW_UP_WEIGHT = 0.5
CACHE_SIZE = 64
MIN_DOCUMENTS = 20

STOP_WORDS = frozenset('''
a ai aie aient aies ait as au aucun aucune aupres aussi autre autres aux avaient avais avait avant avec avez aviez avoir avons ayant
bien c ca car ce ceci cela celle celles celui cependant ces cet cette ceux chaque chez ci comme comment d dans de des deja depuis
dois doit donc donne donner dont du elle elles en encore entre es est et etaient etais etait ete etes etre eu eux explique expliquer
fait faire fais faut furent fut ici il ils j je jusqu l la le les leur leurs lors lui m ma mais me meme memes mes moi mon n ne ni
nos notre nous on ont ou par parce pas peu peut peuvent plus pour pourquoi qu quand que quel quelle quelles quels qui quoi sa sans
se ses si sie sien soi soit sommes son sont sous suis sur t ta te tes toi ton tous tout toute toutes tres tu un une unes uns vos
votre vous vu y
about after again all also am an and any are as at be because been before being both but by can could did do does doing during
each few for from further had has have having he her here hers him his how if in into is it its just me more most my no nor not of
off on once only or other our out over own same she should so some such than that the their them then there these they this those
through to too under until up very was we were what when where which while who whom why will with would you your
'''.split())


def normalize(text):
    """Accent- and case-insensitive form shared by the index and the questions."""
    text = str(text or '').replace('œ', 'oe').replace('Œ', 'OE').replace('æ', 'ae').replace('Æ', 'AE')
    text = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
    return text.casefold()


def fold(token):
    # Light French plural folding: « fonctions » and « fonction » share one term.
    return token[:-1] if len(token) > 4 and token[-1] in 'sx' else token


def tokenize(text):
    return [fold(t) for t in re.findall(r'[a-z0-9]+', normalize(text)) if len(t) >= 2 and t not in STOP_WORDS]


def search_text(*parts):
    return ' '.join(tokenize(' '.join(p for p in parts if p)))


def query_terms(question, previous_question=''):
    """Weights per term: the current question counts fully, the previous one helps follow-ups such as « et pourquoi ? »."""
    terms = {t: FOLLOW_UP_WEIGHT for t in tokenize(previous_question)}
    terms.update({t: 1.0 for t in tokenize(question)})
    return terms


@dataclass
class Corpus:
    ids: list
    kinds: list
    frequencies: list
    lengths: list
    document_frequency: Counter
    average_length: float


_cache = OrderedDict()
_cache_lock = threading.Lock()


def load_corpus(source_type, scope_id, content_version):
    key = (source_type, scope_id, content_version)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    rows = KnowledgeChunk.objects.filter(source_type=source_type, scope_id=scope_id).order_by('order').values_list('id', 'source_kind', 'search_text')
    ids, kinds, frequencies, lengths, df = [], [], [], [], Counter()
    for pk, kind, text in rows:
        counts = Counter(text.split())
        ids.append(pk); kinds.append(kind); frequencies.append(counts); lengths.append(sum(counts.values()))
        df.update(counts.keys())
    corpus = Corpus(ids, kinds, frequencies, lengths, df, (sum(lengths) / len(lengths)) if lengths else 0.0)
    with _cache_lock:
        _cache[key] = corpus
        while len(_cache) > CACHE_SIZE: _cache.popitem(last=False)
    return corpus


def forget(source_type, scope_id):
    with _cache_lock:
        for key in [k for k in _cache if k[:2] == (source_type, scope_id)]: del _cache[key]


def bm25(corpus, terms):
    scores = []
    if not corpus.ids or not terms: return scores
    # Pseudo-documents keep idf meaningful in tiny scopes: with one note, plain BM25 gives every term an idf near 0.3
    # and the absolute threshold would refuse every question.
    total = max(len(corpus.ids), MIN_DOCUMENTS)
    average = corpus.average_length or 1.0
    idf = {t: math.log(1 + (total - corpus.document_frequency[t] + 0.5) / (corpus.document_frequency[t] + 0.5))
        for t in terms if corpus.document_frequency[t]}
    if not idf: return scores
    for index, counts in enumerate(corpus.frequencies):
        score = 0.0
        for term, weight in terms.items():
            tf = counts.get(term)
            if not tf or term not in idf: continue
            score += weight * idf[term] * tf * (K1 + 1) / (tf + K1 * (1 - B + B * corpus.lengths[index] / average))
        if score:
            if corpus.kinds[index] == 'VALIDATED': score *= VALIDATED_BOOST
            scores.append((score, index))
    return scores


@dataclass
class Hit:
    chunk: KnowledgeChunk
    score: float


def retrieve(source_type, scope_id, content_version, question, previous_question='', *, top_k=TOP_K, min_score=None):
    """Best chunks above the threshold; an empty list means the question is outside the course."""
    threshold = settings.ASSISTANT_MIN_SCORE if min_score is None else min_score
    terms = query_terms(question, previous_question)
    for attempt in range(2):
        corpus = load_corpus(source_type, scope_id, content_version)
        ranked = sorted(bm25(corpus, terms), key=lambda item: (-item[0], item[1]))
        best = [(score, corpus.ids[index]) for score, index in ranked[:top_k] if score >= threshold]
        if not best: return []
        chunks = KnowledgeChunk.objects.in_bulk([pk for _, pk in best])
        if attempt or len(chunks) == len(best): break
        # A version can come back (a note added, then deleted) after a rebuild gave its chunks new ids:
        # the cached corpus would then name chunks that no longer exist.
        forget(source_type, scope_id)
    return [Hit(chunks[pk], round(score, 4)) for score, pk in best if pk in chunks]
