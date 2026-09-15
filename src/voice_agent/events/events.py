"""Event dataclasses published by the voice agent to the HUD."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class MicLevel:
    rms: float
    ts: float


@dataclass(frozen=True)
class AudioChunk:
    data: bytes
    sample_rate: int
    ts: float


@dataclass(frozen=True)
class TranscriptPartial:
    text: str
    ts: float


@dataclass(frozen=True)
class TranscriptFinal:
    text: str
    language: str | None
    ts: float


@dataclass(frozen=True)
class LLMToken:
    token: str
    ts: float


@dataclass(frozen=True)
class LLMComplete:
    text: str
    ts: float


@dataclass(frozen=True)
class AudioOutputStart:
    ts: float


@dataclass(frozen=True)
class AudioOutputBytes:
    data: bytes
    ts: float


@dataclass(frozen=True)
class AudioOutputEnd:
    duration_ms: int
    ts: float


@dataclass(frozen=True)
class LatencySample:
    stage: str
    ms: float
    ts: float


@dataclass(frozen=True)
class Error:
    message: str
    source: str
    ts: float
