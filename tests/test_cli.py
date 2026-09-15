"""Tests for the interactive Rich CLI."""
import asyncio
import io
import sys
import pytest

from voice_agent.config import VoiceAgentConfig
from voice_agent.cli import RichCLI


@pytest.mark.asyncio
async def test_cli_handles_status_command(monkeypatch):
    cfg = VoiceAgentConfig()
    cli = RichCLI(cfg)
    cli.console = cli.console.__class__(file=io.StringIO(), force_terminal=False)  # capture

    fake_speak_calls: list[str] = []
    async def fake_speak(text: str) -> None:
        fake_speak_calls.append(text)
    cli._speak = fake_speak  # type: ignore[assignment]

    sys.stdin = io.StringIO("/status\n/quit\n")
    await cli.run()

    out = cli.console.file.getvalue()
    assert "voice" in out
    assert "alloy" in out or "default_voice" in out or "status" in out
    assert fake_speak_calls == []


@pytest.mark.asyncio
async def test_cli_changes_voice_and_speed():
    cfg = VoiceAgentConfig()
    cli = RichCLI(cfg)
    cli.console = cli.console.__class__(file=io.StringIO(), force_terminal=False)

    async def no_speak(text: str) -> None:
        pass
    cli._speak = no_speak  # type: ignore[assignment]

    sys.stdin = io.StringIO("/voice onyx\n/speed 1.5\n/status\n/quit\n")
    await cli.run()

    out = cli.console.file.getvalue()
    assert "onyx" in out
    assert "1.50" in out


@pytest.mark.asyncio
async def test_cli_user_turn_triggers_tts():
    cfg = VoiceAgentConfig()
    cli = RichCLI(cfg)
    cli.console = cli.console.__class__(file=io.StringIO(), force_terminal=False)

    spoken: list[tuple[str, str, float]] = []

    async def fake_speak(text: str) -> None:
        spoken.append((text, cli.state.voice_id, cli.state.speed))
    cli._speak = fake_speak  # type: ignore[assignment]

    sys.stdin = io.StringIO("/voice nova\nolá mundo\n/quit\n")
    await cli.run()

    assert len(spoken) == 1
    text, voice, speed = spoken[0]
    assert "olá mundo" in text
    assert voice == "nova"


@pytest.mark.asyncio
async def test_cli_rejects_bad_speed():
    cfg = VoiceAgentConfig()
    cli = RichCLI(cfg)
    cli.console = cli.console.__class__(file=io.StringIO(), force_terminal=False)

    async def no_speak(text: str) -> None:
        pass
    cli._speak = no_speak  # type: ignore[assignment]

    sys.stdin = io.StringIO("/speed 99\n/quit\n")
    await cli.run()
    out = cli.console.file.getvalue()
    assert "usage" in out.lower()
