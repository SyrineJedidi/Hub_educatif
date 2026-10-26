import logging
import re
import time
from django.db import DatabaseError, IntegrityError
from django.utils import timezone
from django_mongodb_backend import transaction
from classrooms.services import Conflict
from .models import KnowledgeChunk, ScopeIndex
from .retrieval import search_text

CHUNK_SIZE = 1200
OVERLAP = 200
MAX_CHUNKS = 5000
# Bump when the chunking changes, so every index is rebuilt once.
INDEX_FORMAT = '2'

logger = logging.getLogger('assistant')


def word_slices(text, size):
    """Cut a long paragraph into slices of at most size characters, never inside a word."""
    slices, current = [], ''
    for word in text.split(' '):
        while len(word) > size:
            if current: slices.append(current); current = ''
            slices.append(word[:size]); word = word[size:]
        if current and len(current) + 1 + len(word) > size:
            slices.append(current); current = word
        else:
            current = f'{current} {word}' if current else word
    if current: slices.append(current)
    return slices


def paragraphs(text):
    for block in re.split(r'\n\s*\n', str(text or '').replace('\r\n', '\n')):
        lines = [' '.join(line.split()) for line in block.split('\n')]
        paragraph = '\n'.join(line for line in lines if line)
        if not paragraph: continue
        if len(paragraph) <= CHUNK_SIZE: yield paragraph
        else: yield from word_slices(paragraph.replace('\n', ' '), CHUNK_SIZE)


def overlap_tail(text):
    if len(text) <= OVERLAP: return ''
    tail = text[-OVERLAP:]
    if not text[-OVERLAP - 1].isspace():
        cut = re.search(r'\s', tail)
        tail = tail[cut.end():] if cut else ''
    return tail.strip()


def pack(pieces):
    """Group (paragraph, segment) pairs into chunks of about CHUNK_SIZE characters; each chunk repeats the end of the previous one
    and is located by the segment of its first new paragraph."""
    chunks, current, start, fresh = [], [], None, False
    for text, origin in pieces:
        length = sum(len(p) + 2 for p in current)
        if fresh and length + len(text) > CHUNK_SIZE:
            chunks.append(('\n\n'.join(current), start))
            tail = overlap_tail(chunks[-1][0])
            current, start, fresh = ([tail] if tail else []), None, False
        if not fresh: start = origin
        current.append(text); fresh = True
    if fresh: chunks.append(('\n\n'.join(current), start))
    return chunks


def build_chunks(source_type, scope_id, segments):
    groups, key, pieces, meta = [], None, [], None
    for segment in segments:
        segment_key = (segment.source_kind, segment.source_id, segment.chapter_title, segment.page)
        if segment_key != key:
            if pieces: groups.append((meta, pieces))
            key, pieces, meta = segment_key, [], segment
        pieces.extend((p, segment) for p in paragraphs(segment.text))
    if pieces: groups.append((meta, pieces))
    chunks = []
    for meta, group_pieces in groups:
        # A recording's chunks start at different moments: the time and the link come from the chunk's own first segment.
        for text, origin in pack(group_pieces):
            if len(chunks) >= MAX_CHUNKS: return chunks
            chunks.append(KnowledgeChunk(source_type=source_type, scope_id=str(scope_id), order=len(chunks) + 1,
                source_kind=meta.source_kind, source_id=meta.source_id, source_title=meta.source_title[:200],
                chapter_title=(meta.chapter_title or '')[:200], page=meta.page, start_seconds=origin.start_seconds,
                url=(origin.url or '')[:300], text=text[:2000], search_text=search_text(meta.source_title, meta.chapter_title, text)))
    return chunks


def ensure_index(provider, scope_id):
    """Rebuild the scope's chunks when its content changed; concurrent rebuilds are serialised by a compare-and-swap."""
    scope_id = str(scope_id)
    version = f'{INDEX_FORMAT}:{provider.version(scope_id)}'
    lookup = {'source_type': provider.source_type, 'scope_id': scope_id}
    index = ScopeIndex.objects.filter(**lookup).first()
    if index and index.content_version == version: return index
    started = time.monotonic()
    chunks = build_chunks(provider.source_type, scope_id, provider.segments(scope_id))
    build_ms = int((time.monotonic() - started) * 1000)
    if not index:
        try: index = ScopeIndex.objects.create(**lookup)
        except IntegrityError: index = ScopeIndex.objects.get(**lookup)
    for attempt in range(3):
        if index.content_version == version: return index
        try:
            with transaction.atomic():
                claimed = ScopeIndex.objects.filter(pk=index.pk, content_version=index.content_version).update(
                    content_version=version, chunks_count=len(chunks), built_at=timezone.now(), build_ms=build_ms)
                if claimed:
                    KnowledgeChunk.objects.filter(**lookup).delete()
                    KnowledgeChunk.objects.bulk_create(chunks)
            if claimed:
                logger.info('assistant index rebuilt source_type=%s scope_id=%s chunks=%s build_ms=%s', provider.source_type, scope_id, len(chunks), build_ms)
        except DatabaseError:
            if attempt == 2: raise Conflict()
        index = ScopeIndex.objects.get(pk=index.pk)
    if index.content_version != version: raise Conflict()
    return index
