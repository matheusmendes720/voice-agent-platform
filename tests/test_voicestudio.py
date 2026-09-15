"""Tests for VoiceStudio client (mocked)."""
import asyncio
import pytest
from voice_agent.voice.voicestudio import VoiceStudioClient, SynthesisResult


class TestVoiceStudioClient:
    def test_initialization(self):
        client = VoiceStudioClient("http://127.0.0.1:3900")
        assert client.base_url == "http://127.0.0.1:3900"

    def test_synthesis_result(self):
        result = SynthesisResult(audio_bytes=b"test", duration_ms=100)
        assert result.audio_bytes == b"test"
        assert result.duration_ms == 100


@pytest.mark.asyncio
async def test_voicestudio_publishes_tts_events(monkeypatch):
    from voice_agent.hud.events import AudioOutputStart, AudioOutputEnd, LatencySample
    from voice_agent.hud.bus import EventBus

    bus = EventBus()
    sub = bus.subscribe()
    vs = VoiceStudioClient(bus=bus)

    class FakeResp:
        status_code = 200
        content = b"\x00\x00" * 48000  # 1s of silence at 24kHz
        def raise_for_status(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("httpx.post", lambda *a, **k: FakeResp())
    vs.synthesize(text="olá")

    events = []
    for _ in range(4):
        try:
            ev = await asyncio.wait_for(sub.next(), timeout=0.5)
            events.append(ev)
        except asyncio.TimeoutError:
            break
    await bus.close()

    assert any(isinstance(e, AudioOutputStart) for e in events)
    assert any(isinstance(e, AudioOutputEnd) for e in events)
    assert any(isinstance(e, LatencySample) and e.stage == "tts" for e in events)


@pytest.mark.asyncio
async def test_voicestudio_publishes_asr_event(monkeypatch):
    from voice_agent.hud.events import TranscriptFinal, LatencySample
    from voice_agent.hud.bus import EventBus

    bus = EventBus()
    sub = bus.subscribe()
    vs = VoiceStudioClient(bus=bus)

    class FakeResp:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"text": "olá", "language": "pt"}
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("httpx.post", lambda *a, **k: FakeResp())
    vs.transcribe(audio_bytes=b"\x00\x00" * 480)

    evs = []
    for _ in range(3):
        try:
            ev = await asyncio.wait_for(sub.next(), timeout=0.5)
            evs.append(ev)
        except asyncio.TimeoutError:
            break
    await bus.close()

    assert any(isinstance(e, TranscriptFinal) and e.text == "olá" for e in evs)
    assert any(isinstance(e, LatencySample) and e.stage == "asr" for e in evs)


def test_voicestudio_no_bus_is_silent(monkeypatch):
    # When bus is None, synthesize/transcribe must not raise.
    vs = VoiceStudioClient()

    class FakeResp:
        status_code = 200
        content = b"\x00\x00" * 100
        def raise_for_status(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("httpx.post", lambda *a, **k: FakeResp())
    out = vs.synthesize(text="oi")
    assert out.audio_bytes == b"\x00\x00" * 100

    class FakeJsonResp:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"text": "x"}
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("httpx.post", lambda *a, **k: FakeJsonResp())
    out2 = vs.transcribe(audio_bytes=b"\x00\x00" * 10)
    assert out2.text == "x"
