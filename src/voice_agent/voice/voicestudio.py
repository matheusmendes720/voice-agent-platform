"""VoiceStudio HTTP client for TTS and ASR."""
from __future__ import annotations
import io
import time
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
import httpx

if TYPE_CHECKING:
    from ..hud.bus import EventBus


@dataclass
class TranscriptResult:
    text: str
    pinyin: str | None = None


@dataclass
class SynthesisResult:
    audio_bytes: bytes
    duration_ms: int
    sample_rate: int = 24000


@dataclass
class PersonaProfile:
    voice_id: str
    speed: float = 1.0
    instruct: str | None = None
    language: str | None = None
    model: str | None = None
    guidance_scale: float | None = None


class VoiceStudioClient:
    """HTTP client for VoiceStudio API (TTS + ASR)."""

    def __init__(self, base_url: str = "http://127.0.0.1:3900", bus: "EventBus | None" = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.bus = bus

    def _publish(self, event: Any) -> None:
        if self.bus is not None:
            self.bus.publish(event)

    def synthesize(
        self,
        text: str,
        profile_id: str = "alloy",
        response_format: str = "pcm",
        speed: float = 1.0,
        **kwargs: Any,
    ) -> SynthesisResult:
        """Generate speech via VoiceStudio TTS."""
        from ..hud.events import AudioOutputStart, AudioOutputEnd, LatencySample

        payload: dict[str, Any] = {
            "input": text,
            "voice": profile_id,
            "response_format": response_format,
            "speed": speed,
        }
        for k in ("model", "instruct", "language", "guidance_scale"):
            if k in kwargs and kwargs[k] is not None:
                payload[k] = kwargs[k]

        self._publish(AudioOutputStart(ts=time.monotonic()))
        t0 = time.monotonic()
        try:
            with httpx.post(
                f"{self.base_url}/v1/audio/speech",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            ) as resp:
                resp.raise_for_status()
                audio_bytes = resp.content
        finally:
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            self._publish(LatencySample(stage="tts", ms=elapsed_ms, ts=time.monotonic()))

        duration_ms = int(len(audio_bytes) / 24000 / 2 * 1000) if response_format == "pcm" else 0
        self._publish(AudioOutputEnd(duration_ms=duration_ms, ts=time.monotonic()))
        return SynthesisResult(audio_bytes=audio_bytes, duration_ms=duration_ms, sample_rate=24000)

    async def stream_synthesize(
        self,
        text: str,
        profile_id: str = "alloy",
        response_format: str = "pcm",
        speed: float = 1.0,
    ) -> AsyncIterator[bytes]:
        """Stream synthesis (yields all bytes at once)."""
        result = self.synthesize(text, profile_id, response_format, speed)
        yield result.audio_bytes

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 24000) -> TranscriptResult:
        """Transcribe audio bytes via /v1/audio/transcriptions."""
        from ..hud.events import TranscriptFinal, LatencySample

        if audio_bytes[:4] != b"RIFF":
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sample_rate)
                w.writeframes(audio_bytes)
            audio_bytes = buf.getvalue()

        files = {"file": ("recording.wav", audio_bytes, "audio/wav")}
        t0 = time.monotonic()
        data: dict[str, Any] = {}
        try:
            with httpx.post(
                f"{self.base_url}/v1/audio/transcriptions",
                files=files,
                data={"model": "whisper"},
                timeout=60.0,
            ) as resp:
                resp.raise_for_status()
                data = resp.json()
        finally:
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            self._publish(LatencySample(stage="asr", ms=elapsed_ms, ts=time.monotonic()))

        text = data.get("text", "")
        language = data.get("language")
        self._publish(TranscriptFinal(text=text, language=language, ts=time.monotonic()))
        return TranscriptResult(text=text)

    def is_available(self) -> bool:
        """Check if VoiceStudio is reachable."""
        try:
            with httpx.get(f"{self.base_url}/model/status", timeout=3.0) as r:
                return r.status_code == 200
        except Exception:
            return False
