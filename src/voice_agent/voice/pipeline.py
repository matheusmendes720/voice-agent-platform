"""Audio pipeline for capture and playback."""
from __future__ import annotations
import time
import numpy as np
import sounddevice as sd
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..hud.bus import EventBus


@dataclass
class AudioChunk:
    """Represents an audio chunk."""
    data: np.ndarray
    sample_rate: int
    is_speech: bool = True


class AudioPipeline:
    """Handles audio capture and playback."""

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_ms: int = 100,
        channels: int = 1,
        threshold: float = 500.0,
        bus: "EventBus | None" = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_ms / 1000)
        self.channels = channels
        self.threshold = threshold
        self.bus = bus
        self._stream: sd.InputStream | None = None

    def _publish_mic(self, rms: float) -> None:
        if self.bus is None:
            return
        from ..hud.events import MicLevel
        self.bus.publish(MicLevel(rms=float(rms), ts=time.monotonic()))

    def _publish_chunk(self, pcm_bytes: bytes) -> None:
        if self.bus is None:
            return
        from ..hud.events import AudioChunk as HudAudioChunk
        self.bus.publish(HudAudioChunk(data=pcm_bytes, sample_rate=self.sample_rate, ts=time.monotonic()))

    # Test hooks — keep tiny; used by tests/test_pipeline_events.py.
    def _publish_mic_for_test(self, rms: float) -> None:
        self._publish_mic(rms)

    def _publish_chunk_for_test(self, pcm_bytes: bytes, sample_rate: int) -> None:
        self._publish_chunk(pcm_bytes)

    def read(self) -> AudioChunk:
        """Read one audio chunk from microphone."""
        if self._stream is None:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                blocksize=self.chunk_size,
            )
        data, _ = self._stream.read(self.chunk_size)
        rms = float(np.sqrt(np.mean(data.astype(float) ** 2)))
        self._publish_mic(rms)
        is_speech = rms > self.threshold
        chunk = AudioChunk(data=data.flatten(), sample_rate=self.sample_rate, is_speech=is_speech)
        if is_speech:
            self._publish_chunk(chunk.data.tobytes())
        return chunk

    def play(self, audio_bytes: bytes, sample_rate: int = 24000) -> None:
        """Play audio bytes (16-bit PCM)."""
        audio = np.frombuffer(audio_bytes, dtype=np.int16)
        if audio.size == 0:
            return
        sd.play(audio, samplerate=sample_rate)
        sd.wait()

    def close(self) -> None:
        """Close audio stream."""
        if self._stream:
            self._stream.close()
            self._stream = None
