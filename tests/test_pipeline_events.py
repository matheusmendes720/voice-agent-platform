"""Tests that AudioPipeline publishes MicLevel + AudioChunk events."""
import asyncio
import pytest
from voice_agent.events.events import MicLevel, AudioChunk
from voice_agent.events.bus import EventBus
from voice_agent.voice.pipeline import AudioPipeline


@pytest.mark.asyncio
async def test_pipeline_publishes_mic_level_and_chunk():
    bus = EventBus()
    sub = bus.subscribe()
    pipeline = AudioPipeline(bus=bus, sample_rate=16000, chunk_ms=10)
    # Use dedicated test hooks to publish deterministically without opening a mic.
    pipeline._publish_mic_for_test(rms=0.42)
    pipeline._publish_chunk_for_test(b"\x00\x01" * 160, pipeline.sample_rate)
    ev1 = await asyncio.wait_for(sub.next(), timeout=0.5)
    ev2 = await asyncio.wait_for(sub.next(), timeout=0.5)
    assert isinstance(ev1, MicLevel)
    assert ev1.rms == pytest.approx(0.42)
    assert isinstance(ev2, AudioChunk)
    assert ev2.sample_rate == 16000
    assert ev2.data == b"\x00\x01" * 160
    await bus.close()


@pytest.mark.asyncio
async def test_pipeline_no_bus_is_silent():
    # When bus is None, hooks are no-ops (must not raise).
    pipeline = AudioPipeline()
    pipeline._publish_mic_for_test(rms=0.1)
    pipeline._publish_chunk_for_test(b"\x00\x00", 16000)
