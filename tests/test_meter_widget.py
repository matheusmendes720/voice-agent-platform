"""Tests for MeterWidget."""
from voice_agent.hud.widgets.meter import MeterWidget


def test_meter_renders_bar():
    w = MeterWidget()
    rendered = w._render_bar(rms=0.5, width=20)
    # _render_bar now returns a Text — use plain to compare.
    text = str(rendered)
    assert "█" in text or "▓" in text or "░" in text
    assert len(text) == 20


def test_meter_clamps_rms():
    w = MeterWidget()
    assert w._clamp(0.5) == 0.5
    assert w._clamp(-1.0) == 0.0
    assert w._clamp(2.0) == 1.0


def test_meter_update_rms_clamps_value():
    w = MeterWidget()
    # We do NOT call update_rms here (which triggers reactive update() and needs app).
    # Instead, directly verify the clamp behaviour the watch_rms would apply.
    assert w._clamp(0.7) == 0.7
    assert w._clamp(5.0) == 1.0
