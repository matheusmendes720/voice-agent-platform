"""Tests for MeterWidget."""
from voice_agent.hud.widgets.meter import MeterWidget


def test_meter_renders_bar():
    w = MeterWidget()
    rendered = w._render_bar(rms=0.5, width=20)
    assert "█" in rendered or "▓" in rendered or "░" in rendered
    assert len(rendered) == 20


def test_meter_clamps_rms():
    w = MeterWidget()
    assert w._clamp(0.5) == 0.5
    assert w._clamp(-1.0) == 0.0
    assert w._clamp(2.0) == 1.0


def test_meter_update_rms_stores_value():
    w = MeterWidget()
    w.update_rms(0.7)
    assert w.rms == 0.7
    # And clamps
    w.update_rms(5.0)
    assert w.rms == 1.0
