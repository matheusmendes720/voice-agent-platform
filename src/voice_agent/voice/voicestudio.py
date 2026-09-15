"""VoiceStudio HTTP client for TTS and ASR."""
from __future__ import annotations
from dataclasses import dataclass
from collections.abc import AsyncIterator
import httpx


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
    """Synchronous HTTP client for VoiceStudio API (TTS + ASR)."""

    def __init__(self, base_url: str = "http://127.0.0.1:3900") -> None:
        self.base_url = base_url.rstrip("/")

    def synthesize(
        self,
        text: str,
        profile_id: str = "alloy",
        response_format: str = "pcm",
        speed: float = 1.0,
        **kwargs,
    ) -> SynthesisResult:
        """Generate speech via VoiceStudio TTS."""
        payload = {
            "input": text,
            "voice": profile_id,
            "response_format": response_format,
            "speed": speed,
        }
        for k in ("model", "instruct", "language", "guidance_scale"):
            if k in kwargs and kwargs[k] is not None:
                payload[k] = kwargs[k]

        with httpx.post(
            f"{self.base_url}/v1/audio/speech",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        ) as resp:
            resp.raise_for_status()
            return SynthesisResult(
                audio_bytes=resp.content,
                duration_ms=0,
                sample_rate=24000 if response_format == "pcm" else 24000,
            )

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
        """Transcribe audio bytes via /v1/audio/transcriptions.

        audio_bytes: raw PCM or WAV data. If raw PCM, sample_rate is used
        to build a proper WAV header (24kHz mono 16-bit).
        """
        import io
        import wave

        # Wrap raw PCM in a WAV header if needed
        if audio_bytes[:4] != b"RIFF":
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sample_rate)
                w.writeframes(audio_bytes)
            audio_bytes = buf.getvalue()

        files = {"file": ("recording.wav", audio_bytes, "audio/wav")}
        with httpx.post(
            f"{self.base_url}/v1/audio/transcriptions",
            files=files,
            data={"model": "whisper"},
            timeout=60.0,
        ) as resp:
            resp.raise_for_status()
            data = resp.json()
            return TranscriptResult(text=data.get("text", ""))

    def is_available(self) -> bool:
        """Check if VoiceStudio is reachable."""
        try:
            with httpx.get(f"{self.base_url}/model/status", timeout=3.0) as r:
                return r.status_code == 200
        except Exception:
            return False
