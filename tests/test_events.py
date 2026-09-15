"""Tests for HUD event dataclasses."""
from dataclasses import FrozenInstanceError
import pytest
from voice_agent.hud.events import MicLevel, TranscriptFinal


def test_miclevel_is_frozen():
    e = MicLevel(rms=0.5, ts=1.0)
    with pytest.raises(FrozenInstanceError):
        e.rms = 0.7  # type: ignore[misc]


def test_transcriptfinal_optional_language():
    e = TranscriptFinal(text="olá", language=None, ts=1.0)
    assert e.text == "olá"
    assert e.language is None


def test_events_have_ts():
    e = MicLevel(rms=0.5, ts=123.456)
    assert e.ts == pytest.approx(123.456)
