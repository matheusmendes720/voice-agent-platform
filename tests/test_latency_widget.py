"""Tests for LatencyWidget."""
from voice_agent.hud.widgets.latency import LatencyWidget


def test_latency_stores_per_stage():
    w = LatencyWidget()
    w.update("tts", 3500)
    w.update("asr", 20000)
    snap = w.snapshot()
    assert snap["tts"] == 3500
    assert snap["asr"] == 20000


def test_latency_render_includes_both_stages():
    w = LatencyWidget()
    w.update("tts", 3500)
    w.update("asr", 20000)
    out = w._render()
    assert "tts" in out and "asr" in out
