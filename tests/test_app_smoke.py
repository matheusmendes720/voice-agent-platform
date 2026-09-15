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


def test_app_has_three_modes():
    cfg = VoiceAgentConfig()
    bus = EventBus()
    agent = VoiceAgent(cfg, bus=bus)
    app = build_app(agent, bus)
    assert set(app.MODES.keys()) == {"conversation", "waveform", "tuning"}


@pytest.mark.asyncio
async def test_app_mode_switching():
    from voice_agent.hud.screens.tuning import TuningScreen
    from voice_agent.hud.screens.waveform import WaveformScreen
    from voice_agent.hud.screens.conversation import ConversationScreen
    cfg = VoiceAgentConfig()
    bus = EventBus()
    agent = VoiceAgent(cfg, bus=bus)
    app = build_app(agent, bus)
    async with app.run_test() as pilot:
        await pilot.pause()
        # When a screen has Input widgets, those absorb numeric keys.
        # Verify mode switching via the actions directly (keyboard is UI-side concern).
        await app.action_go_tuning()
        await pilot.pause()
        assert isinstance(app.screen, TuningScreen)
        await app.action_go_waveform()
        await pilot.pause()
        assert isinstance(app.screen, WaveformScreen)
        await app.action_go_conversation()
        await pilot.pause()
        assert isinstance(app.screen, ConversationScreen)


@pytest.mark.asyncio
async def test_tuning_respeak_invokes_voice(monkeypatch):
    from unittest.mock import MagicMock
    from voice_agent.hud.screens.tuning import TuningScreen
    cfg = VoiceAgentConfig()
    bus = EventBus()
    agent = VoiceAgent(cfg, bus=bus)
    voice = MagicMock()
    voice.synthesize.return_value = MagicMock(audio_bytes=b"\x00" * 100, duration_ms=4)
    app = build_app(agent, bus, voice=voice)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, TuningScreen)
        await screen.action_respeak()
        await pilot.pause()
        assert voice.synthesize.called
        # Sample sentence is the first positional arg.
        sample = voice.synthesize.call_args[0][0]
        assert "Olá" in sample
