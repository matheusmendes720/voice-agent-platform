"""Tests for the interactive Rich CLI."""
import asyncio
import io
import pytest

from voice_agent.config import VoiceAgentConfig
from voice_agent.cli import RichCLI


def _make_cli(monkeypatch) -> RichCLI:
    cfg = VoiceAgentConfig()
    cli = RichCLI(cfg)
    cli.console = cli.console.__class__(file=io.StringIO(), force_terminal=False)
    # offline: VoiceStudio unreachable is OK
    cli.vs.is_available = lambda: True  # type: ignore[assignment]
    return cli


@pytest.mark.asyncio
async def test_cli_handles_status_command(monkeypatch):
    cli = _make_cli(monkeypatch)
    spoken: list[str] = []

    async def fake_speak(text: str) -> None:
        spoken.append(text)
    cli._speak = fake_speak  # type: ignore[assignment]

    monkeypatch.setattr("builtins.input", lambda *a, **k: "/quit\n")
    await cli.run()

    assert spoken == []  # nothing spoken — we just quit


@pytest.mark.asyncio
async def test_cli_changes_voice_and_speed(monkeypatch):
    cli = _make_cli(monkeypatch)
    async def no_speak(text: str) -> None:
        pass
    cli._speak = no_speak  # type: ignore[assignment]

    inputs = iter(["/voice onyx", "/speed 1.5", "/quit"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(inputs))
    await cli.run()

    assert cli.state.voice == "onyx"
    assert cli.state.speed == pytest.approx(1.5)


@pytest.mark.asyncio
async def test_cli_user_turn_triggers_say(monkeypatch):
    cli = _make_cli(monkeypatch)
    spoken: list[str] = []

    async def fake_speak(text: str) -> None:
        spoken.append(text)
    cli._speak = fake_speak  # type: ignore[assignment]

    inputs = iter(["/voice nova", "olá mundo", "/quit"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(inputs))
    await cli.run()

    assert len(spoken) == 1
    assert "olá mundo" in spoken[0]


@pytest.mark.asyncio
async def test_cli_rejects_bad_speed(monkeypatch):
    cli = _make_cli(monkeypatch)
    async def no_speak(text: str) -> None:
        pass
    cli._speak = no_speak  # type: ignore[assignment]

    inputs = iter(["/speed 99", "/quit"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(inputs))
    await cli.run()

    # bad speed should leave state.speed unchanged (default 1.0)
    assert cli.state.speed == pytest.approx(1.0)
