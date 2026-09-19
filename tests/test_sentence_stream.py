"""Tests for sentence-boundary streaming parser."""
import pytest
from voice_agent.agent.sentence_stream import parse_sentences_fast, sentences_from_tokens


def test_parse_simple_two_sentences():
    out = parse_sentences_fast("Olá! Tudo bem?")
    assert out == ["Olá!", "Tudo bem?"]


def test_parse_handles_no_terminator():
    out = parse_sentences_fast("olá sem fim")
    assert out == ["olá sem fim"]


def test_parse_handles_ellipsis():
    out = parse_sentences_fast("olá… tudo bem.")
    assert out == ["olá…", "tudo bem."]


def test_parse_chains_sentences():
    out = parse_sentences_fast("Sim. Não. Talvez!")
    assert out == ["Sim.", "Não.", "Talvez!"]


def test_parse_no_terminator_returns_full_text():
    """If the LLM never adds a terminator, the whole reply is one chunk."""
    out = parse_sentences_fast("olá sem fim")
    assert out == ["olá sem fim"]


def test_parse_keeps_abbreviations_together():
    """"O Sr." must not split — "Matheus" continues into the same sentence."""
    out = parse_sentences_fast("O Sr. Matheus disse oi. Eu respondi.")
    assert out == ["O Sr. Matheus disse oi.", "Eu respondi."]


def test_parse_handles_dra():
    out = parse_sentences_fast("Dra. Maria chegou cedo. Ela está aqui.")
    assert out == ["Dra. Maria chegou cedo.", "Ela está aqui."]


@pytest.mark.asyncio
async def test_sentences_from_tokens_flushes_tail():
    async def gen():
        for tok in ["olá", " como", " vai", "?"]:
            yield tok

    out = []
    async for s in sentences_from_tokens(gen()):
        out.append(s)
    assert out == ["olá como vai?"]


@pytest.mark.asyncio
async def test_sentences_from_tokens_emits_mid_stream():
    async def gen():
        for tok in ["OK", ". ", "Próxima", "."]:
            yield tok

    out = []
    async for s in sentences_from_tokens(gen()):
        out.append(s)
    assert out == ["OK.", "Próxima."]
