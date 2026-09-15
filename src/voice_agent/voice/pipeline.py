"""Audio pipeline for capture and playback."""
from __future__ import annotations
import numpy as np
import sounddevice as sd
from dataclasses import dataclass


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
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_ms / 1000)
        self.channels = channels
        self.threshold = threshold
        self._stream: sd.InputStream | None = None

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
        rms = np.sqrt(np.mean(data.astype(float) ** 2))
        is_speech = rms > self.threshold
        return AudioChunk(data=data.flatten(), sample_rate=self.sample_rate, is_speech=is_speech)

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
