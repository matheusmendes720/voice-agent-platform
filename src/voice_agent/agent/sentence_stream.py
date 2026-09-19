"""Sentence-boundary streaming: buffer LLM tokens, flush complete sentences."""
from __future__ import annotations
import asyncio
import re
from typing import AsyncIterator

_BOUNDARY = re.compile(r"([.!?…])")
# Tokens too short risk mid-word splits ("O Sr."). Hold them until either a
# real sentence follows or the buffer would otherwise stall.
_MIN_SENTENCE_CHARS = 25
# Common abbreviations whose trailing "." must NOT split.
_KEEP_TOGETHER = re.compile(
    r"\b(Sr|Sra|Dr|Dra|Prof|Profª|St|Mr|Mrs|Ms|vs|etc|e|p|ex|nº|n)\.$",
    re.IGNORECASE,
)


async def sentences_from_tokens(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """Yield each complete sentence as soon as we see its terminator.

    Anything left after the stream ends is flushed as a final partial sentence.
    """
    buf = ""
    async for tok in tokens:
        buf += tok
        while True:
            m = _BOUNDARY.search(buf)
            if not m:
                break
            end = m.end()
            sentence = buf[:end].strip()
            buf = buf[end:]
            if not sentence:
                continue
            # Don't flush tiny fragments — wait for more context.
            if len(sentence) < _MIN_SENTENCE_CHARS and buf and not re.match(r"^[\s]", buf):
                # Put it back and wait for the next chunk.
                buf = sentence + " " + buf
                break
            yield sentence
    tail = buf.strip()
    if tail:
        yield tail


def parse_sentences_fast(text: str) -> list[str]:
    """Split a fully-formed reply into sentences (sync helper, used for tests).

    Skips splitting on common abbreviations so "O Sr. Matheus" stays together.
    Always emits at least one chunk — if no split happened, returns the full
    text as one sentence (so per-sentence TTS still works for short replies).
    """
    # Build matches without emitting fragments containing abbreviations.
    parts: list[str] = []
    buf = ""
    for i, ch in enumerate(text):
        buf += ch
        if ch in ".!?…":
            tail = buf.rstrip()
            # If the current chunk ends with a known abbreviation, don't split.
            if _KEEP_TOGETHER.search(tail):
                continue
            s = buf.strip()
            if s:
                parts.append(s)
            buf = ""
    tail = buf.strip()
    if tail:
        parts.append(tail)
    # Edge case: no terminators at all → return the whole text as one chunk.
    if not parts and text.strip():
        parts.append(text.strip())
    return parts


async def synthesize_sentences(text: str, synthesize, *, play) -> None:
    """Split `text` into sentences and synthesize + play each in order.

    Returns when the last sentence has been played. synthesize(text) -> bytes.
    play(bytes) -> awaitable (blocks until playback done).
    """
    for sentence in parse_sentences_fast(text):
        audio = await asyncio.to_thread(synthesize, sentence)
        if audio:
            await play(audio)
