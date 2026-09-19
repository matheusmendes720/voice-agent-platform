"""Sentence-boundary streaming: buffer LLM tokens, flush complete sentences."""
from __future__ import annotations
import asyncio
import re
from typing import AsyncIterator

_BOUNDARY = re.compile(r"([.!?…])")


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
            if sentence:
                yield sentence
    tail = buf.strip()
    if tail:
        yield tail


def parse_sentences_fast(text: str) -> list[str]:
    """Split a fully-formed reply into sentences (sync helper, used for tests)."""
    parts = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in ".!?…":
            s = buf.strip()
            if s:
                parts.append(s)
            buf = ""
    tail = buf.strip()
    if tail:
        parts.append(tail)
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
