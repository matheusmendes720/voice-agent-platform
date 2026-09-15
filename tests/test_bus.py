"""Tests for the EventBus."""
import asyncio
import pytest
from voice_agent.events.events import MicLevel, TranscriptFinal
from voice_agent.events.bus import EventBus


@pytest.mark.asyncio
async def test_publish_delivers_to_subscriber():
    bus = EventBus()
    sub = bus.subscribe()
    bus.publish(MicLevel(rms=0.5, ts=1.0))
    ev = await asyncio.wait_for(sub.next(), timeout=0.5)
    assert isinstance(ev, MicLevel)
    assert ev.rms == pytest.approx(0.5)
    await bus.close()


@pytest.mark.asyncio
async def test_multiple_subscribers_each_get_copy():
    bus = EventBus()
    a = bus.subscribe()
    b = bus.subscribe()
    bus.publish(TranscriptFinal(text="hi", language="pt", ts=2.0))
    ea = await asyncio.wait_for(a.next(), timeout=0.5)
    eb = await asyncio.wait_for(b.next(), timeout=0.5)
    assert ea.text == eb.text == "hi"
    await bus.close()


@pytest.mark.asyncio
async def test_close_stops_iteration():
    bus = EventBus()
    sub = bus.subscribe()
    await bus.close()
    with pytest.raises(StopAsyncIteration):
        await sub.next()


@pytest.mark.asyncio
async def test_publish_after_close_is_noop():
    bus = EventBus()
    await bus.close()
    bus.publish(MicLevel(rms=0.1, ts=1.0))  # must not raise
