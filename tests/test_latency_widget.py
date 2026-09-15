"""Tests for LatencyWidget."""
from voice_agent.hud.widgets.latency import LatencyWidget


def test_latency_stores_per_stage():
    w = LatencyWidget()
    w.update = lambda *_a, **_k: None  # type: ignore[assignment]
    w.set_stage = LatencyWidget.update.__get__(w)  # restore original update
    # Bypass the visual update, just test the data layer.
    w._values["tts"] = 3500.0
    w._values["asr"] = 20000.0
    snap = w.snapshot()
    assert snap["tts"] == 3500
    assert snap["asr"] == 20000


def test_latency_render_includes_both_stages():
    w = LatencyWidget()
    w.update = lambda *_a, **_k: None  # type: ignore[assignment]
    w._values["tts"] = 3500.0
    w._values["asr"] = 20000.0
    out = w._render_str()
    assert "tts" in out and "asr" in out
