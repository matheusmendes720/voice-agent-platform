"""Tests that the Textual App builds with the default config."""
import pytest
from voice_agent.hud.app import build_app
from voice_agent.hud.bus import EventBus
from voice_agent.config import VoiceAgentConfig
from voice_agent.agent.core import VoiceAgent


def test_app_builds_with_default_config():
    cfg = VoiceAgentConfig()
    bus = EventBus()
    agent = VoiceAgent(cfg, bus=bus)
    app = build_app(agent, bus)
    assert app.TITLE == "voice-agent"


@pytest.mark.asyncio
async def test_app_pump_logs_events(monkeypatch):
    from voice_agent.hud.events import MicLevel
    cfg = VoiceAgentConfig()
    bus = EventBus()
    agent = VoiceAgent(cfg, bus=bus)
    app = build_app(agent, bus)
    bus.publish(MicLevel(rms=0.5, ts=1.0))
    # Just confirm the app object exposes the bus for the pump task.
    assert app.bus is bus
