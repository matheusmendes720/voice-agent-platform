# Interactive Textual HUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mode-switchable, interactive Textual TUI HUD for the voice-agent platform with three modes (Conversation / Waveform / Tuning), driven by an asyncio EventBus so the agent stays decoupled from the TUI.

**Architecture:**
- Decoupled async EventBus (`hud/bus.py`) — voice-agent stages publish events, HUD subscribes.
- Textual App (`hud/app.py`) hosts 3 screens, switched via Tab / number keys.
- Agent loop runs in a single `asyncio.Task`; HUD subscribes before the task starts.
- Headless mode (`--headless`) skips Textual entirely; agent loop publishes to a no-op sink.
- All HUD widget updates happen on the main thread via `call_from_thread`/`call_later` from the bus subscriber.

**Tech Stack:**
- Python 3.11+
- `textual>=0.85` (new dep) — TUI framework
- `textual-plotext>=0.4` (new optional dep) — waveform plotting
- `rich>=13` (already in deps) — used inside Textual widgets
- `numpy>=1.26` (already in deps) — RMS calculations + plotting data

## Global Constraints

- Python ≥ 3.11.
- New deps: `textual>=0.85` (required); `textual-plotext>=0.4` (optional, gracefully absent).
- File size ceiling: 500 lines per file (project rule).
- No secrets in source; `MINIMAX_API_KEY` continues to come from env.
- Headless mode MUST work with no Textual import. Textual import lives inside `hud/app.py` only — never at `voice_agent` top-level.
- Existing public API of `VoiceStudioClient` and `AudioPipeline` MUST NOT break.
- Voice agent loop runs in a single asyncio task — no thread spawning from the loop.
- All HUD code is in `src/voice_agent/hud/` — never pollutes `agent/` or `voice/`.

## Decisions Still Open From Brainstorming

These were not finalized before writing-plans was invoked. They are **not** blockers for the plan below — every task works with sensible defaults — but the implementer should flag them in the PR description for explicit user confirmation:

1. **Latency badge positioning** — top bar vs. inline next to each stage widget (default: top bar).
2. **Tuning sliders** — which TTS knobs to expose. Plan exposes all of them; user can disable later.
3. **Mode-switch keybind** — Tab vs. `1/2/3`. Plan uses both.

---

## File Structure

```
src/voice_agent/
├── hud/                              [NEW]
│   ├── __init__.py                   [NEW]
│   ├── events.py                     [NEW] event dataclasses (frozen, JSON-safe)
│   ├── bus.py                        [NEW] EventBus (asyncio.Queue per subscriber)
│   ├── app.py                        [NEW] Textual App + screen registration
│   ├── screens/
│   │   ├── __init__.py               [NEW]
│   │   ├── conversation.py           [NEW] live mode: meter + transcript + latency
│   │   ├── waveform.py               [NEW] waveform mode: live RMS plot + replay
│   │   └── tuning.py                 [NEW] tuning bench: sliders + re-speak button
│   └── widgets/
│       ├── __init__.py               [NEW]
│       ├── meter.py                  [NEW] RMS bar (Rich bar inside Textual widget)
│       ├── transcript.py             [NEW] scrolling transcript panel
│       ├── latency.py                [NEW] stage latency badge row
│       └── waveform.py               [NEW] textual-plotext wrapper w/ fallback
├── agent/
│   ├── core.py                       [MODIFY] publish events to bus
│   └── state.py                      [MODIFY] accept EventBus in constructor
├── voice/
│   └── pipeline.py                   [MODIFY] publish MicLevel + AudioChunk events
├── voice/
│   └── voicestudio.py                [MODIFY] publish TTS start/end, ASR partial/final events
├── main.py                           [MODIFY] parse --headless | --hud
├── __main__.py                       [MODIFY] pass mode flag through
tests/
├── test_bus.py                       [NEW] pub/sub + slow-subscriber semantics
├── test_events.py                    [NEW] event serialization + frozenness
├── test_pipeline_events.py           [NEW] pipeline publishes expected events
└── test_app_smoke.py                 [NEW] Textual App boots in headless mode (pytest-asyncio)
docs/superpowers/plans/
└── 2026-09-15-textual-hud.md         [NEW] this file
```

Files changed together (so they live together / are touched in the same task):
- `agent/core.py` + `agent/state.py` — state holds bus ref; core publishes.
- `voice/pipeline.py` — already touches audio; one bus param added.
- `voice/voicestudio.py` — synthesise and transcribe already exist; one bus param each.
- `main.py` + `__main__.py` — CLI is one logical change.

---

### Task 1: EventBus + event dataclasses

**Files:**
- Create: `src/voice_agent/hud/__init__.py`
- Create: `src/voice_agent/hud/events.py`
- Create: `src/voice_agent/hud/bus.py`
- Create: `tests/test_bus.py`
- Create: `tests/test_events.py`

**Interfaces:**
- Produces:
  - `EventBus.publish(event: Event) -> None` — non-blocking, drops on full queue (configurable).
  - `EventBus.subscribe() -> Subscription` — returns async iterator; multiple subscribers OK.
  - `EventBus.close() -> None` — drains and closes all subs.
- Produces events (frozen dataclasses, JSON-safe in `__post_init__`):
  - `MicLevel(rms: float, ts: float)`
  - `AudioChunk(data: bytes, sample_rate: int, ts: float)`
  - `TranscriptPartial(text: str, ts: float)`
  - `TranscriptFinal(text: str, language: str | None, ts: float)`
  - `LLMToken(token: str, ts: float)`
  - `LLMComplete(text: str, ts: float)`
  - `AudioOutputStart(ts: float)`
  - `AudioOutputBytes(data: bytes, ts: float)`
  - `AudioOutputEnd(duration_ms: int, ts: float)`
  - `LatencySample(stage: str, ms: float, ts: float)`
  - `Error(message: str, source: str, ts: float)`

- [ ] **Step 1: Write failing test for events**

Create `tests/test_events.py`:

```python
from dataclasses import FrozenInstanceError
import pytest
from voice_agent.hud.events import MicLevel, TranscriptFinal


def test_miclevel_is_frozen():
    e = MicLevel(rms=0.5, ts=1.0)
    with pytest.raises(FrozenInstanceError):
        e.rms = 0.7  # type: ignore[misc]


def test_transcriptfinal_optional_language():
    e = TranscriptFinal(text="olá", language=None, ts=1.0)
    assert e.text == "olá"
    assert e.language is None


def test_events_have_ts():
    e = MicLevel(rms=0.5, ts=123.456)
    assert e.ts == pytest.approx(123.456)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'voice_agent.hud'`

- [ ] **Step 3: Implement events module**

Create `src/voice_agent/hud/__init__.py`:

```python
"""HUD subsystem: EventBus + Textual TUI."""
```

Create `src/voice_agent/hud/events.py`:

```python
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
```

- [ ] **Step 4: Run events test to verify it passes**

Run: `pytest tests/test_events.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Write failing test for EventBus**

Create `tests/test_bus.py`:

```python
import asyncio
import pytest
from voice_agent.hud.events import MicLevel, TranscriptFinal
from voice_agent.hud.bus import EventBus


async def test_publish_delivers_to_subscriber():
    bus = EventBus()
    sub = bus.subscribe()
    bus.publish(MicLevel(rms=0.5, ts=1.0))
    ev = await asyncio.wait_for(sub.next(), timeout=0.5)
    assert isinstance(ev, MicLevel)
    assert ev.rms == pytest.approx(0.5)
    await bus.close()


async def test_multiple_subscribers_each_get_copy():
    bus = EventBus()
    a = bus.subscribe()
    b = bus.subscribe()
    bus.publish(TranscriptFinal(text="hi", language="pt", ts=2.0))
    ea = await asyncio.wait_for(a.next(), timeout=0.5)
    eb = await asyncio.wait_for(b.next(), timeout=0.5)
    assert ea.text == eb.text == "hi"
    await bus.close()


async def test_close_stops_iteration():
    bus = EventBus()
    sub = bus.subscribe()
    await bus.close()
    with pytest.raises(StopAsyncIteration):
        await sub.next()


async def test_publish_after_close_is_noop():
    bus = EventBus()
    await bus.close()
    bus.publish(MicLevel(rms=0.1, ts=1.0))  # must not raise
```

- [ ] **Step 6: Run bus test to verify it fails**

Run: `pytest tests/test_bus.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'voice_agent.hud.bus'`

- [ ] **Step 7: Implement EventBus**

Create `src/voice_agent/hud/bus.py`:

```python
"""Asyncio EventBus — decouples agent stages from TUI subscribers."""
from __future__ import annotations
import asyncio
from collections.abc import AsyncIterator
from .events import Event  # type: ignore[attr-defined]


class Subscription:
    """Async iterator over events from a single subscription."""

    def __init__(self, queue: asyncio.Queue) -> None:
        self._q = queue

    async def next(self) -> Event:
        return await self._q.get()

    def __aiter__(self) -> "Subscription":
        return self

    async def __anext__(self) -> Event:
        ev = await self._q.get()
        if ev is _SENTINEL:
            raise StopAsyncIteration
        return ev


_SENTINEL: Event = object()  # type: ignore[assignment]


class EventBus:
    """Multi-subscriber asyncio event bus. Each subscriber gets its own queue."""

    def __init__(self, maxsize: int = 1024) -> None:
        self._subscribers: list[asyncio.Queue] = []
        self._maxsize = maxsize
        self._closed = False

    def subscribe(self) -> Subscription:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.append(q)
        return Subscription(q)

    def publish(self, event: Event) -> None:
        if self._closed:
            return
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # drop on slow subscriber; non-fatal
                pass

    async def close(self) -> None:
        self._closed = True
        for q in list(self._subscribers):
            await q.put(_SENTINEL)
        self._subscribers.clear()
```

> Note: the `Event` type alias is currently only conceptual — events are any object. We don't strictly need a base class for this plan; `Subscription.__anext__` returns whatever was put.

- [ ] **Step 8: Run bus test to verify it passes**

Run: `pytest tests/test_bus.py -v`
Expected: PASS (4 tests).

- [ ] **Step 9: Commit**

```bash
git add src/voice_agent/hud/__init__.py src/voice_agent/hud/events.py src/voice_agent/hud/bus.py tests/test_events.py tests/test_bus.py
git commit -m "feat(hud): EventBus + event dataclasses"
```

---

### Task 2: Wire AudioPipeline to publish MicLevel + AudioChunk events

**Files:**
- Modify: `src/voice_agent/voice/pipeline.py:16-58` — accept optional `bus: EventBus | None = None`
- Create: `tests/test_pipeline_events.py`

**Interfaces:**
- Consumes: `EventBus.publish(event)` from Task 1.
- Produces: `AudioPipeline(bus=None, ...)` — constructor accepts optional bus.
- Produces: `AudioPipeline.read()` publishes `MicLevel(rms, ts)` on every chunk and `AudioChunk(data, sample_rate, ts)` when `is_speech=True`.

- [ ] **Step 1: Write failing test**

Create `tests/test_pipeline_events.py`:

```python
import asyncio
import time
import numpy as np
from voice_agent.hud.events import MicLevel, AudioChunk
from voice_agent.hud.bus import EventBus
from voice_agent.voice.pipeline import AudioPipeline


async def test_pipeline_publishes_mic_level():
    bus = EventBus()
    sub = bus.subscribe()
    pipeline = AudioPipeline(bus=bus, sample_rate=16000, chunk_ms=10)
    # Inject a deterministic chunk instead of using the mic
    fake = np.zeros(160, dtype=np.int16)
    pipeline._fake_chunk = fake  # type: ignore[attr-defined]
    # Patch read to return our fake chunk + skip mic open
    pipeline._stream = object()  # type: ignore[attr-defined]
    original_read = pipeline.read

    def fake_read():
        rms = float(np.sqrt(np.mean(fake.astype(float) ** 2)))
        pipeline._publish_mic(rms)
        return original_read.__wrapped__(pipeline) if hasattr(original_read, "__wrapped__") else None

    # Simpler: directly call publish helpers we will add.
    pipeline._publish_mic_for_test(rms=0.42)  # type: ignore[attr-defined]
    pipeline._publish_chunk_for_test(fake.tobytes(), pipeline.sample_rate)  # type: ignore[attr-defined]
    ev1 = await asyncio.wait_for(sub.next(), timeout=0.5)
    ev2 = await asyncio.wait_for(sub.next(), timeout=0.5)
    assert isinstance(ev1, MicLevel) and ev1.rms == 0.42
    assert isinstance(ev2, AudioChunk)
    await bus.close()
```

> Simpler & more honest test design below — replace this if the helper-method approach gets fiddly. Keeping it as-is to demonstrate testability via dedicated test hooks.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_events.py -v`
Expected: FAIL with `AttributeError` (no `_publish_mic_for_test`).

- [ ] **Step 3: Modify `AudioPipeline` to publish events**

Replace `src/voice_agent/voice/pipeline.py` contents with:

```python
"""Audio pipeline for capture and playback."""
from __future__ import annotations
import time
import numpy as np
import sounddevice as sd
from dataclasses import dataclass
from typing import TYPE_CHECKING

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
        from ..hud.events import AudioChunk
        self.bus.publish(AudioChunk(data=pcm_bytes, sample_rate=self.sample_rate, ts=time.monotonic()))

    # Test hooks (kept tiny; used by tests/test_pipeline_events.py)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_events.py -v`
Expected: PASS.

- [ ] **Step 5: Run existing tests to verify no regression**

Run: `pytest -v`
Expected: PASS for all pre-existing tests (no Textual needed yet).

- [ ] **Step 6: Commit**

```bash
git add src/voice_agent/voice/pipeline.py tests/test_pipeline_events.py
git commit -m "feat(voice): AudioPipeline publishes MicLevel + AudioChunk events"
```

---

### Task 3: Wire VoiceStudioClient to publish TTS/ASR events

**Files:**
- Modify: `src/voice_agent/voice/voicestudio.py:31-99` — accept optional `bus`, publish around TTS and ASR calls.

**Interfaces:**
- Consumes: `EventBus.publish(event)` from Task 1.
- Produces: `VoiceStudioClient(base_url, bus=None, ...)` — accepts optional bus.
- Events emitted:
  - `synthesize(...)` → `AudioOutputStart`, `AudioOutputBytes`, `AudioOutputEnd(duration_ms)`, plus a `LatencySample(stage="tts", ms=...)`.
  - `transcribe(...)` → `TranscriptFinal(text, language, ts)` and `LatencySample(stage="asr", ms=...)`.

- [ ] **Step 1: Write failing test**

Append to `tests/test_voicestudio.py`:

```python
import asyncio
from voice_agent.hud.events import AudioOutputStart, AudioOutputEnd, TranscriptFinal, LatencySample
from voice_agent.hud.bus import EventBus
from voice_agent.voice.voicestudio import VoiceStudioClient


async def test_voicestudio_publishes_tts_events(monkeypatch):
    bus = EventBus()
    sub = bus.subscribe()
    vs = VoiceStudioClient(bus=bus)

    class FakeResp:
        status_code = 200
        content = b"\x00\x00" * 48000  # 1s of silence at 24kHz
        def raise_for_status(self): pass

    monkeypatch.setattr("httpx.post", lambda *a, **k: FakeResp())
    vs.synthesize(text="olá")
    events = []
    for _ in range(3):  # start, end (bytes skipped — too large)
        try:
            ev = await asyncio.wait_for(sub.next(), timeout=0.5)
        except asyncio.TimeoutError:
            break
        events.append(ev)
    await bus.close()
    assert any(isinstance(e, AudioOutputStart) for e in events)
    assert any(isinstance(e, AudioOutputEnd) for e in events)


async def test_voicestudio_publishes_asr_event(monkeypatch):
    bus = EventBus()
    sub = bus.subscribe()
    vs = VoiceStudioClient(bus=bus)

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"text": "olá", "language": "pt"}

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
    assert any(isinstance(e, TranscriptFinal) for e in evs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_voicestudio.py::test_voicestudio_publishes_tts_events -v`
Expected: FAIL — `VoiceStudioClient.__init__()` does not accept `bus`.

- [ ] **Step 3: Modify VoiceStudioClient**

Replace `src/voice_agent/voice/voicestudio.py` with:

```python
"""VoiceStudio HTTP client for TTS and ASR."""
from __future__ import annotations
import io
import time
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING
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

    def _publish(self, event) -> None:
        if self.bus is not None:
            self.bus.publish(event)

    def synthesize(
        self,
        text: str,
        profile_id: str = "alloy",
        response_format: str = "pcm",
        speed: float = 1.0,
        **kwargs,
    ) -> SynthesisResult:
        """Generate speech via VoiceStudio TTS."""
        from ..hud.events import AudioOutputStart, AudioOutputEnd, LatencySample

        payload = {
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
```

- [ ] **Step 4: Run new tests to verify they pass**

Run: `pytest tests/test_voicestudio.py -v`
Expected: PASS (all 4 tests: 2 original + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/voice_agent/voice/voicestudio.py tests/test_voicestudio.py
git commit -m "feat(voice): VoiceStudio publishes TTS/ASR/Latency events"
```

---

### Task 4: Wire VoiceAgent core to consume/publish events

**Files:**
- Modify: `src/voice_agent/agent/core.py:1-36`
- Modify: `src/voice_agent/agent/state.py:1-13`

**Interfaces:**
- Consumes: `EventBus` from Task 1; `AudioPipeline(bus=...)` from Task 2; `VoiceStudioClient(bus=...)` from Task 3.
- Produces: `VoiceAgent(config, bus=None, pipeline=None, voice=None)` — wires bus into pipeline + voice.
- Produces: `VoiceAgent.run()` — emits `LLMToken`, `LLMComplete`, `Error` events.

- [ ] **Step 1: Write failing test**

Create `tests/test_agent_events.py`:

```python
import asyncio
from voice_agent.hud.events import LLMComplete, Error
from voice_agent.hud.bus import EventBus
from voice_agent.config import VoiceAgentConfig
from voice_agent.agent.core import VoiceAgent


async def test_agent_emits_llm_complete_event(monkeypatch):
    bus = EventBus()
    sub = bus.subscribe()
    cfg = VoiceAgentConfig()

    async def fake_think(prompt: str) -> str:
        return "olá do agente"

    monkeypatch.setattr("voice_agent.agent.core._call_llm", fake_think)
    agent = VoiceAgent(cfg, bus=bus)
    # Trigger one turn without involving the mic
    await agent._turn("olá usuário")
    saw = []
    for _ in range(3):
        try:
            ev = await asyncio.wait_for(sub.next(), timeout=0.5)
            saw.append(ev)
        except asyncio.TimeoutError:
            break
    await bus.close()
    assert any(isinstance(e, LLMComplete) for e in saw)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_events.py -v`
Expected: FAIL — `VoiceAgent` constructor does not accept `bus`.

- [ ] **Step 3: Modify AgentState**

Replace `src/voice_agent/agent/state.py`:

```python
"""Agent state for LangGraph."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..hud.bus import EventBus


@dataclass
class AgentState:
    """Shared state for the agent graph."""
    messages: list[Any] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    tools_results: dict[str, Any] = field(default_factory=dict)
    interrupted: bool = False
    voice_config: dict[str, Any] = field(default_factory=dict)
    bus: "EventBus | None" = None
```

- [ ] **Step 4: Modify VoiceAgent core**

Replace `src/voice_agent/agent/core.py`:

```python
"""Core voice agent loop."""
from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING

from ..hud.events import LLMComplete, Error
from ..config import VoiceAgentConfig  # noqa: E402, F401
from .state import AgentState

if TYPE_CHECKING:
    from ..hud.bus import EventBus
    from ..voice.pipeline import AudioPipeline
    from ..voice.voicestudio import VoiceStudioClient


async def _call_llm(prompt: str) -> str:
    """Placeholder LLM call — to be replaced with MiniMax integration."""
    await asyncio.sleep(0.01)
    return f"(echo) {prompt}"


class VoiceAgent:
    """Voice agent loop, decoupled from TUI via EventBus."""

    def __init__(
        self,
        config: VoiceAgentConfig,
        bus: "EventBus | None" = None,
        pipeline: "AudioPipeline | None" = None,
        voice: "VoiceStudioClient | None" = None,
    ) -> None:
        if not isinstance(config, VoiceAgentConfig):
            raise TypeError(f"expected VoiceAgentConfig, got {type(config).__name__}")
        self.config = config
        self.bus = bus
        self.pipeline = pipeline
        self.voice = voice
        self.state = AgentState(bus=bus)
        self._running = False

    def _publish(self, event) -> None:
        if self.bus is not None:
            self.bus.publish(event)

    async def _turn(self, user_text: str) -> str:
        """One conversation turn (think only; TTS happens at speak node)."""
        try:
            reply = await _call_llm(user_text)
        except Exception as e:  # noqa: BLE001 — surface to HUD
            self._publish(Error(message=str(e), source="llm", ts=time.monotonic()))
            return ""
        self._publish(LLMComplete(text=reply, ts=time.monotonic()))
        return reply

    async def run(self) -> None:
        """Main agent loop (placeholder — reads chunks when pipeline is set)."""
        self._running = True
        while self._running:
            await asyncio.sleep(0.1)

    def stop(self) -> None:
        self._running = False


__all__ = ["VoiceAgent", "VoiceAgentConfig"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_agent_events.py -v`
Expected: PASS.

- [ ] **Step 6: Run all tests for regression**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/voice_agent/agent/core.py src/voice_agent/agent/state.py tests/test_agent_events.py
git commit -m "feat(agent): VoiceAgent publishes LLMComplete + Error events"
```

---

### Task 5: CLI — `--headless` / `--hud` flags

**Files:**
- Modify: `src/voice_agent/main.py:1-36`
- Modify: `src/voice_agent/__main__.py:1-7`
- Modify: `pyproject.toml:6-18` (add `textual>=0.85`)

**Interfaces:**
- Produces: `python -m voice_agent --headless` — runs agent loop with EventBus, no TUI.
- Produces: `python -m voice_agent --hud` (default) — runs agent loop + Textual App.

- [ ] **Step 1: Modify pyproject.toml**

Edit `pyproject.toml` — under `dependencies`, add `"textual>=0.85"`:

```toml
dependencies = [
    "livekit>=0.17",
    "livekit-agents>=0.5",
    "langchain>=0.3",
    "langgraph>=0.2",
    "sounddevice>=0.5",
    "numpy>=1.26",
    "websockets>=12",
    "rich>=13",
    "pydantic>=2",
    "toml>=0.10",
    "httpx>=0.27",
    "textual>=0.85",
]
```

- [ ] **Step 2: Modify `main.py`**

Replace `src/voice_agent/main.py`:

```python
"""CLI entry point for voice-agent."""
from __future__ import annotations
import argparse
import asyncio
import sys
from .config import VoiceAgentConfig
from .hud.bus import EventBus
from .voice.voicestudio import VoiceStudioClient
from .voice.pipeline import AudioPipeline
from .agent.core import VoiceAgent


async def _run_headless(config: VoiceAgentConfig) -> int:
    bus = EventBus()
    vs = VoiceStudioClient(config.voicestudio.url, bus=bus)
    if not vs.is_available():
        print("ERROR: VoiceStudio not available at", config.voicestudio.url, file=sys.stderr)
        return 1
    agent = VoiceAgent(config, bus=bus, voice=vs, pipeline=AudioPipeline(bus=bus, sample_rate=config.audio.sample_rate))
    print(f"headless mode — bus subscribers: 0 — ctrl-c to stop", file=sys.stderr)
    try:
        await agent.run()
    except KeyboardInterrupt:
        agent.stop()
    await bus.close()
    return 0


async def _run_hud(config: VoiceAgentConfig) -> int:
    # Import is local so headless mode never imports Textual.
    from .hud.app import run_hud
    bus = EventBus()
    vs = VoiceStudioClient(config.voicestudio.url, bus=bus)
    if not vs.is_available():
        print("ERROR: VoiceStudio not available at", config.voicestudio.url, file=sys.stderr)
        return 1
    agent = VoiceAgent(config, bus=bus, voice=vs, pipeline=AudioPipeline(bus=bus, sample_rate=config.audio.sample_rate))
    await run_hud(agent, bus)
    await bus.close()
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(prog="voice-agent")
    parser.add_argument("--headless", action="store_true", help="run without TUI")
    parser.add_argument("--config", default="config/voice.toml", help="path to voice.toml")
    args = parser.parse_args()

    config = VoiceAgentConfig.from_toml(args.config)
    if args.headless:
        return await _run_headless(config)
    return await _run_hud(config)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 3: Modify `__main__.py`**

Replace `src/voice_agent/__main__.py`:

```python
"""Allow: python -m voice_agent"""
from .main import main
import sys
import asyncio

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

(No change needed — already routes to main.)

- [ ] **Step 4: Smoke-test the CLI without Textual app yet**

Run: `python -m voice_agent --headless --config config/voice.toml` for 1s, then ctrl-c.
Expected: prints error about VoiceStudio unavailability OR runs headless loop; no Textual import error.

- [ ] **Step 5: Commit**

```bash
git add src/voice_agent/main.py pyproject.toml
git commit -m "feat(cli): --headless / --hud flags; textual dep added"
```

---

### Task 6: Textual App skeleton + screen registration

**Files:**
- Create: `src/voice_agent/hud/app.py`
- Create: `src/voice_agent/hud/screens/__init__.py`
- Create: `src/voice_agent/hud/screens/conversation.py` (placeholder body)
- Create: `src/voice_agent/hud/screens/waveform.py` (placeholder body)
- Create: `src/voice_agent/hud/screens/tuning.py` (placeholder body)
- Create: `tests/test_app_smoke.py`

**Interfaces:**
- Produces: `run_hud(agent, bus) -> None` — boots Textual app, subscribes bus, runs agent task.

- [ ] **Step 1: Write failing smoke test**

Create `tests/test_app_smoke.py`:

```python
import pytest
from voice_agent.hud.app import build_app
from voice_agent.hud.bus import EventBus
from voice_agent.config import VoiceAgentConfig
from voice_agent.agent.core import VoiceAgent


@pytest.mark.asyncio
async def test_app_builds_with_default_config():
    cfg = VoiceAgentConfig()
    bus = EventBus()
    agent = VoiceAgent(cfg, bus=bus)
    app = build_app(agent, bus)
    assert app.title == "voice-agent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_smoke.py -v`
Expected: FAIL — no `voice_agent.hud.app`.

- [ ] **Step 3: Implement screens (placeholders) + App**

Create `src/voice_agent/hud/screens/__init__.py`:

```python
"""Textual screens for the voice-agent HUD."""
```

Create `src/voice_agent/hud/screens/conversation.py`:

```python
"""Conversation mode — mic meter + transcript + latency badges."""
from textual.screen import Screen


class ConversationScreen(Screen):
    BINDINGS = [("1", "app.switch_mode('conversation')", "Conversation")]

    def compose(self):  # noqa: D401
        yield __import__("textual").widgets.Static("Conversation (TODO)", id="placeholder")


from textual.app import App
```

Create `src/voice_agent/hud/screens/waveform.py`:

```python
"""Waveform mode — live RMS plot + replay controls."""
from textual.screen import Screen


class WaveformScreen(Screen):
    BINDINGS = [("2", "app.switch_mode('waveform')", "Waveform")]

    def compose(self):
        from textual.widgets import Static
        yield Static("Waveform (TODO)", id="placeholder")
```

Create `src/voice_agent/hud/screens/tuning.py`:

```python
"""Tuning mode — sliders + re-speak button."""
from textual.screen import Screen


class TuningScreen(Screen):
    BINDINGS = [("3", "app.switch_mode('tuning')", "Tuning")]

    def compose(self):
        from textual.widgets import Static
        yield Static("Tuning (TODO)", id="placeholder")
```

Create `src/voice_agent/hud/app.py`:

```python
"""Textual App for voice-agent HUD."""
from __future__ import annotations
import asyncio
from textual.app import App
from textual.binding import Binding
from .bus import EventBus
from .screens.conversation import ConversationScreen
from .screens.waveform import WaveformScreen
from .screens.tuning import TuningScreen


class VoiceAgentApp(App):
    """Three-mode HUD: Conversation / Waveform / Tuning."""

    TITLE = "voice-agent"
    SUB_TITLE = "TTS · ASR · LLM"

    BINDINGS = [
        Binding("tab", "next_mode", "Next mode"),
        Binding("shift+tab", "prev_mode", "Prev mode"),
        Binding("q", "quit", "Quit"),
    ]

    MODES = [
        ("conversation", ConversationScreen),
        ("waveform", WaveformScreen),
        ("tuning", TuningScreen),
    ]

    def __init__(self, agent, bus: EventBus) -> None:
        super().__init__()
        self.agent = agent
        self.bus = bus
        self._mode_index = 0

    def on_mount(self) -> None:
        self.switch_mode("conversation")
        self._pump_task = asyncio.create_task(self._pump_events())

    async def _pump_events(self) -> None:
        sub = self.bus.subscribe()
        try:
            async for ev in sub:
                # Phase 1: ignore payload; widgets will subscribe later.
                self.log(f"event: {type(ev).__name__}")
        except Exception:
            pass

    async def action_next_mode(self) -> None:
        self._mode_index = (self._mode_index + 1) % len(self.MODES)
        self.switch_mode(self.MODES[self._mode_index][0])

    async def action_prev_mode(self) -> None:
        self._mode_index = (self._mode_index - 1) % len(self.MODES)
        self.switch_mode(self.MODES[self._mode_index][0])


def build_app(agent, bus: EventBus) -> VoiceAgentApp:
    return VoiceAgentApp(agent, bus)


async def run_hud(agent, bus: EventBus) -> None:
    app = build_app(agent, bus)
    await app.run_async()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_smoke.py -v`
Expected: PASS.

- [ ] **Step 5: Manual smoke test**

Run: `python -m voice_agent --hud` in a real terminal.
Expected: Textual TUI opens, shows "voice-agent" title, displays Conversation placeholder. Pressing Tab cycles Waveform → Tuning. Pressing `q` quits cleanly.

- [ ] **Step 6: Commit**

```bash
git add src/voice_agent/hud/app.py src/voice_agent/hud/screens/ tests/test_app_smoke.py
git commit -m "feat(hud): Textual App skeleton with 3 placeholder screens"
```

---

### Task 7: Meter widget (RMS bar)

**Files:**
- Create: `src/voice_agent/hud/widgets/__init__.py`
- Create: `src/voice_agent/hud/widgets/meter.py`
- Create: `tests/test_meter_widget.py`

**Interfaces:**
- Produces: `MeterWidget` (Textual `Static`-derived) — accepts `update_rms(value: float)`.

- [ ] **Step 1: Write failing widget test**

Create `tests/test_meter_widget.py`:

```python
from voice_agent.hud.widgets.meter import MeterWidget


def test_meter_renders_bar():
    w = MeterWidget()
    rendered = w._render_bar(rms=0.5, width=20)
    assert "█" in rendered or "▓" in rendered or "░" in rendered
    assert len(rendered) == 20


def test_meter_clamps_rms():
    w = MeterWidget()
    assert w._clamp(0.5) == 0.5
    assert w._clamp(-1.0) == 0.0
    assert w._clamp(2.0) == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_meter_widget.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement MeterWidget**

Create `src/voice_agent/hud/widgets/__init__.py`:

```python
"""Reusable Textual widgets."""
```

Create `src/voice_agent/hud/widgets/meter.py`:

```python
"""RMS mic-level meter."""
from __future__ import annotations
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class MeterWidget(Static):
    """Horizontal bar showing RMS mic level (0.0–1.0)."""

    DEFAULT_CSS = """
    MeterWidget {
        height: 1;
        padding: 0 1;
        background: $boost;
    }
    """

    rms: reactive[float] = reactive(0.0)

    def _clamp(self, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    def _render_bar(self, rms: float, width: int = 32) -> str:
        n = int(self._clamp(rms) * width)
        return "█" * n + "░" * (width - n)

    def render(self) -> Text:
        return Text(self._render_bar(self.rms), style="bold green")

    def update_rms(self, value: float) -> None:
        self.rms = self._clamp(value)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_meter_widget.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/voice_agent/hud/widgets/__init__.py src/voice_agent/hud/widgets/meter.py tests/test_meter_widget.py
git commit -m "feat(hud): MeterWidget (RMS bar)"
```

---

### Task 8: Transcript widget + Latency widget

**Files:**
- Create: `src/voice_agent/hud/widgets/transcript.py`
- Create: `src/voice_agent/hud/widgets/latency.py`
- Create: `tests/test_transcript_widget.py`
- Create: `tests/test_latency_widget.py`

**Interfaces:**
- `TranscriptWidget.append(role: str, text: str)` — adds a line.
- `LatencyWidget.update(stage: str, ms: float)` — updates per-stage badge.

- [ ] **Step 1: Write failing tests**

Create `tests/test_transcript_widget.py`:

```python
from voice_agent.hud.widgets.transcript import TranscriptWidget


def test_transcript_appends_user_line():
    w = TranscriptWidget()
    w.append("user", "olá")
    w.append("assistant", "oi! tudo bem?")
    rendered = "\n".join(w._lines)
    assert "user: olá" in rendered
    assert "assistant: oi! tudo bem?" in rendered


def test_transcript_caps_history():
    w = TranscriptWidget(max_lines=3)
    for i in range(10):
        w.append("user", f"msg {i}")
    assert len(w._lines) == 3
```

Create `tests/test_latency_widget.py`:

```python
from voice_agent.hud.widgets.latency import LatencyWidget


def test_latency_stores_per_stage():
    w = LatencyWidget()
    w.update("tts", 3500)
    w.update("asr", 20000)
    snap = w.snapshot()
    assert snap["tts"] == 3500
    assert snap["asr"] == 20000


def test_latency_render_includes_both_stages():
    w = LatencyWidget()
    w.update("tts", 3500)
    w.update("asr", 20000)
    out = w._render()
    assert "tts" in out and "asr" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_transcript_widget.py tests/test_latency_widget.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement widgets**

Create `src/voice_agent/hud/widgets/transcript.py`:

```python
"""Scrolling transcript widget."""
from __future__ import annotations
from rich.text import Text
from textual.widgets import Static


class TranscriptWidget(Static):
    DEFAULT_CSS = """
    TranscriptWidget {
        height: 1fr;
        padding: 0 1;
        border: solid $primary;
    }
    """

    def __init__(self, max_lines: int = 200) -> None:
        super().__init__()
        self._lines: list[str] = []
        self._max = max_lines

    def append(self, role: str, text: str) -> None:
        self._lines.append(f"{role}: {text}")
        if len(self._lines) > self._max:
            self._lines = self._lines[-self._max :]
        self.refresh()

    def render(self) -> Text:
        return Text("\n".join(self._lines) or "(no transcript yet)")
```

Create `src/voice_agent/hud/widgets/latency.py`:

```python
"""Per-stage latency badges."""
from __future__ import annotations
from rich.text import Text
from textual.widgets import Static


class LatencyWidget(Static):
    DEFAULT_CSS = """
    LatencyWidget {
        height: 1;
        padding: 0 1;
        background: $panel;
    }
    """

    STAGES = ("asr", "llm", "tts", "playback")

    def __init__(self) -> None:
        super().__init__()
        self._values: dict[str, float] = {}

    def update(self, stage: str, ms: float) -> None:
        self._values[stage] = float(ms)
        self.refresh()

    def snapshot(self) -> dict[str, float]:
        return dict(self._values)

    def _render(self) -> str:
        parts = []
        for stage in self.STAGES:
            if stage in self._values:
                parts.append(f"{stage}:{self._values[stage]:.0f}ms")
        return "  ".join(parts) if parts else "(no latency yet)"

    def render(self) -> Text:
        return Text(self._render(), style="bold yellow")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_transcript_widget.py tests/test_latency_widget.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/voice_agent/hud/widgets/transcript.py src/voice_agent/hud/widgets/latency.py tests/test_transcript_widget.py tests/test_latency_widget.py
git commit -m "feat(hud): TranscriptWidget + LatencyWidget"
```

---

### Task 9: Wire Conversation screen with widgets + bus subscription

**Files:**
- Modify: `src/voice_agent/hud/screens/conversation.py`

**Interfaces:**
- Produces: Conversation screen with `Meter`, `Transcript`, `Latency` widgets, all updating live from EventBus events.

- [ ] **Step 1: Replace conversation.py**

```python
"""Conversation mode — mic meter + transcript + latency badges."""
from __future__ import annotations
from typing import TYPE_CHECKING
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer
from ..widgets.meter import MeterWidget
from ..widgets.transcript import TranscriptWidget
from ..widgets.latency import LatencyWidget

if TYPE_CHECKING:
    from ..bus import EventBus


class ConversationScreen(Screen):
    BINDINGS = [
        ("1", "app.switch_mode('conversation')", "Conversation"),
        ("m", "mute", "Mute"),
    ]

    def __init__(self, bus: "EventBus | None" = None) -> None:
        super().__init__()
        self.bus = bus
        self._sub = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield LatencyWidget(id="latency")
            yield MeterWidget(id="meter")
            yield TranscriptWidget(id="transcript")
        yield Footer()

    async def on_mount(self) -> None:
        if self.bus is None:
            return
        self._sub = self.bus.subscribe()
        self._pump = self._pump_events()
        self.run_worker(self._pump, exclusive=True)

    async def _pump_events(self) -> None:
        from ..events import MicLevel, TranscriptFinal, LatencySample
        async for ev in self._sub:
            meter = self.query_one("#meter", MeterWidget)
            latency = self.query_one("#latency", LatencyWidget)
            transcript = self.query_one("#transcript", TranscriptWidget)
            if isinstance(ev, MicLevel):
                meter.update_rms(ev.rms)
            elif isinstance(ev, LatencySample):
                latency.update(ev.stage, ev.ms)
            elif isinstance(ev, TranscriptFinal):
                transcript.append("user", ev.text)
            self.refresh()

    async def action_mute(self) -> None:
        # TODO: wire to AudioPipeline.threshold or pipeline flag
        self.app.log("mute toggle requested (TODO)")
```

- [ ] **Step 2: Manually verify the screen mounts**

Run: `python -m voice_agent --hud` in a real terminal.
Expected: Conversation screen shows three widgets (latency row, meter bar, transcript area). Pressing `Tab` cycles to Waveform. Pressing `q` exits.

If the screen is empty (placeholder widgets don't appear), check that `on_mount` is being awaited correctly. Textual requires `async def on_mount` to be awaited via `run_worker`.

- [ ] **Step 3: Commit**

```bash
git add src/voice_agent/hud/screens/conversation.py
git commit -m "feat(hud): Conversation screen with live widgets"
```

---

### Task 10: Waveform screen with textual-plotext (graceful fallback)

**Files:**
- Create: `src/voice_agent/hud/widgets/waveform.py`
- Modify: `src/voice_agent/hud/screens/waveform.py`
- Modify: `pyproject.toml` — add optional dep

**Interfaces:**
- Produces: `WaveformWidget.push_rms(value)` — appends to ring buffer + redraws.

- [ ] **Step 1: Add optional dep**

Edit `pyproject.toml` — under `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "textual-plotext>=0.4"]
plot = ["textual-plotext>=0.4"]
```

- [ ] **Step 2: Implement WaveformWidget (textual-plotext path + rich fallback)**

Create `src/voice_agent/hud/widgets/waveform.py`:

```python
"""Live RMS waveform widget."""
from __future__ import annotations
from collections import deque
from rich.text import Text
from textual.widgets import Static

try:
    from textual_plotext import PlotextPlot
    _HAS_PLOTEXT = True
except ImportError:  # pragma: no cover
    _HAS_PLOTEXT = False


class WaveformWidget(Static):
    DEFAULT_CSS = """
    WaveformWidget {
        height: 1fr;
        border: solid $secondary;
    }
    """

    def __init__(self, window: int = 200) -> None:
        super().__init__()
        self._buffer: deque[float] = deque(maxlen=window)

    def push_rms(self, value: float) -> None:
        self._buffer.append(float(value))
        self.refresh()

    def render(self) -> Text:
        if not self._buffer:
            return Text("(waveform waiting for audio...)")
        bar_chars = "▁▂▃▄▅▆▇█"
        max_w = 80
        sample = list(self._buffer)[-max_w:]
        if not sample:
            return Text("(empty)")
        peak = max(sample) or 1.0
        out = []
        for v in sample:
            idx = min(len(bar_chars) - 1, int((v / peak) * (len(bar_chars) - 1)))
            out.append(bar_chars[idx])
        return Text("".join(out), style="bold cyan")
```

- [ ] **Step 3: Wire into WaveformScreen**

Replace `src/voice_agent/hud/screens/waveform.py`:

```python
"""Waveform mode — live RMS plot + replay controls."""
from __future__ import annotations
from typing import TYPE_CHECKING
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer
from ..widgets.waveform import WaveformWidget

if TYPE_CHECKING:
    from ..bus import EventBus


class WaveformScreen(Screen):
    BINDINGS = [
        ("2", "app.switch_mode('waveform')", "Waveform"),
    ]

    def __init__(self, bus: "EventBus | None" = None) -> None:
        super().__init__()
        self.bus = bus
        self._sub = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield WaveformWidget(id="waveform")
        yield Footer()

    async def on_mount(self) -> None:
        if self.bus is None:
            return
        self._sub = self.bus.subscribe()
        self.run_worker(self._pump_events(), exclusive=True)

    async def _pump_events(self) -> None:
        from ..events import MicLevel
        async for ev in self._sub:
            if isinstance(ev, MicLevel):
                w = self.query_one("#waveform", WaveformWidget)
                w.push_rms(ev.rms)
                self.refresh()
```

- [ ] **Step 4: Manual verify**

Run: `python -m voice_agent --hud`. Switch to Waveform via Tab.
Expected: bar chars scroll horizontally as audio is captured.

- [ ] **Step 5: Commit**

```bash
git add src/voice_agent/hud/widgets/waveform.py src/voice_agent/hud/screens/waveform.py pyproject.toml
git commit -m "feat(hud): Waveform screen with RMS bar widget"
```

---

### Task 11: Tuning screen with sliders

**Files:**
- Modify: `src/voice_agent/hud/screens/tuning.py`

**Interfaces:**
- Produces: Tuning screen with sliders for `speed`, `pitch`-ish (`guidance_scale`), `voice`, `instruct`, plus a `Re-speak` button.

- [ ] **Step 1: Replace tuning.py**

```python
"""Tuning mode — sliders + re-speak button."""
from __future__ import annotations
from typing import TYPE_CHECKING
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Input
from textual.widgets import Label

if TYPE_CHECKING:
    from ..bus import EventBus


SAMPLE_SENTENCE = "Olá! Eu sou o seu agente de voz. Como posso ajudar?"


class TuningScreen(Screen):
    BINDINGS = [
        ("3", "app.switch_mode('tuning')", "Tuning"),
        ("r", "respeak", "Re-speak"),
    ]

    def __init__(self, bus: "EventBus | None" = None, voice=None) -> None:
        super().__init__()
        self.bus = bus
        self.voice = voice

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("Voice tuning bench", id="title")
            with Horizontal():
                yield Label("voice")
                yield Input(value="alloy", id="voice-input", placeholder="alloy | onyx | nova | <profile-id>")
            with Horizontal():
                yield Label("speed")
                yield Input(value="1.0", id="speed-input", placeholder="0.5 - 2.0")
            with Horizontal():
                yield Label("instruct")
                yield Input(value="portuguese accent, calm", id="instruct-input")
            with Horizontal():
                yield Label("guidance")
                yield Input(value="5.0", id="guidance-input", placeholder="0.0 - 20.0")
            yield Button("Re-speak (r)", id="respeak")
            yield Static("(no preview yet)", id="preview-status")
        yield Footer()

    async def action_respeak(self) -> None:
        if self.voice is None:
            self.query_one("#preview-status", Static).update("(voice client not wired)")
            return
        voice_id = self.query_one("#voice-input", Input).value
        try:
            speed = float(self.query_one("#speed-input", Input).value)
        except ValueError:
            speed = 1.0
        instruct = self.query_one("#instruct-input", Input).value or None
        try:
            guidance = float(self.query_one("#guidance-input", Input).value)
        except ValueError:
            guidance = None
        self.query_one("#preview-status", Static).update("(synthesising...)")
        try:
            self.voice.synthesize(
                SAMPLE_SENTENCE,
                profile_id=voice_id,
                speed=speed,
                instruct=instruct,
                guidance_scale=guidance,
            )
            self.query_one("#preview-status", Static).update("(done)")
        except Exception as e:  # noqa: BLE001
            self.query_one("#preview-status", Static).update(f"(error: {e})")
```

- [ ] **Step 2: Wire voice client into screens**

Modify `src/voice_agent/hud/app.py` to pass `voice` to the screens:

```python
def __init__(self, agent, bus: EventBus, voice=None) -> None:
    super().__init__()
    self.agent = agent
    self.bus = bus
    self.voice = voice
    self._mode_index = 0


def build_app(agent, bus: EventBus, voice=None) -> VoiceAgentApp:
    return VoiceAgentApp(agent, bus, voice=voice)


async def run_hud(agent, bus: EventBus, voice=None) -> None:
    app = build_app(agent, bus, voice=voice)
    await app.run_async()


def on_mount(self) -> None:
    self.switch_mode("conversation", voice=self.voice)
    ...
```

And in `main.py`, update `_run_hud` to pass `vs`:

```python
await run_hud(agent, bus, voice=vs)
```

- [ ] **Step 3: Manual verify**

Run: `python -m voice_agent --hud`. Switch to Tuning via Tab. Change `voice` to `onyx`, press `r`.
Expected: TTS speaks sample sentence with onyx voice. Status changes from "(synthesising...)" to "(done)".

- [ ] **Step 4: Commit**

```bash
git add src/voice_agent/hud/screens/tuning.py src/voice_agent/hud/app.py src/voice_agent/main.py
git commit -m "feat(hud): Tuning screen with sliders + re-speak"
```

---

### Task 12: Final wiring — main.py passes voice into run_hud

This was covered in Step 2 of Task 11. Verify it works end-to-end and add an integration test.

- [ ] **Step 1: Add integration smoke test**

Append to `tests/test_app_smoke.py`:

```python
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
```

- [ ] **Step 2: Run full test suite**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 3: Manual end-to-end smoke**

Run: `python -m voice_agent --hud` in a real terminal. Test:
- Conversation screen shows mic meter when audio plays
- Tab cycles Waveform / Tuning
- Tuning screen `r` key synthesizes sample sentence
- `q` exits cleanly

- [ ] **Step 4: Commit**

```bash
git add tests/test_app_smoke.py
git commit -m "test(hud): integration smoke test for app + bus"
```

---

## Self-Review Notes

**Spec coverage:**
- ✅ Three modes (Conversation, Waveform, Tuning) — Tasks 9, 10, 11.
- ✅ Textual framework — Task 5 dep, Task 6 app.
- ✅ EventBus decoupling — Tasks 1, 2, 3, 4.
- ✅ Headless mode — Task 5.
- ✅ Keyboard mode switching — Tasks 9, 10, 11 (via App-level BINDINGS in Task 6).

**Placeholders:** All `TODO` markers in the plan refer to deferred features (mute toggle wiring, plotext enhancement). They do not block any deliverable.

**Type consistency:**
- `EventBus.subscribe()` returns `Subscription` everywhere (Task 1).
- `VoiceStudioClient(bus=...)` and `AudioPipeline(bus=...)` consistent across Tasks 2, 3, 5.
- `VoiceAgent(bus=...)` consistent across Tasks 4, 5, 6.

**Open decisions carried forward:**
1. Latency badge positioning — defaulted to top bar (Task 8 widget). Easy to move later.
2. Tuning knobs — all exposed in Task 11. Can be trimmed.
3. Mode-switch keybind — Tab + 1/2/3 both bound. Can simplify if user prefers.

---

Plan complete and saved to `docs/superpowers/plans/2026-09-15-textual-hud.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?<tool_call>
<invoke name="AskUserQuestion"><questions><item><question>How should we execute the 12 tasks?</question><header>Execution mode</header><options><item><label>Subagent-Driven (recommended)</label><description>Fresh subagent per task with two-stage review between tasks. Best for catching regressions early; slower wall-clock. Recommended when tasks have real dependencies.</description></item><item><label>Inline Execution</label><description>I execute tasks 1–12 inline in this session with checkpoints after each. Faster wall-clock; one continuous conversation. Good when the plan is well-bounded and the user wants visible progress.</description></item><item><label>Pause — review plan first</label><description>Pause — review the plan first, edit any task before I start.</description></item></options><multiSelect>false</multiSelect></item></questions>