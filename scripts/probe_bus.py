"""Probe the screen subscription wiring — does the pump worker actually drain events?"""
import asyncio
import sys
import os

sys.path.insert(0, r"C:\Users\mathe\code_space\voice-agent\src")

from voice_agent.config import VoiceAgentConfig
from voice_agent.hud.bus import EventBus
from voice_agent.hud.events import MicLevel, LatencySample
from voice_agent.agent.core import VoiceAgent
from voice_agent.voice.voicestudio import VoiceStudioClient
from voice_agent.voice.pipeline import AudioPipeline
from voice_agent.hud.app import VoiceAgentApp


async def main() -> int:
    cfg = VoiceAgentConfig()
    bus = EventBus()
    vs = VoiceStudioClient(bus=bus)
    agent = VoiceAgent(cfg, bus=bus, voice=vs, pipeline=AudioPipeline(bus=bus))
    app = VoiceAgentApp(agent, bus, voice=vs)

    async with app.run_test() as pilot:
        await pilot.pause()
        # After mount, conversation screen should have subscribed.
        await pilot.pause()
        await pilot.pause()
        print(f"subscribers on bus: {len(bus._subscribers)}")
        # Inject events
        for i in range(5):
            bus.publish(MicLevel(rms=min(1.0, 0.1 * (i + 1)), ts=float(i)))
            bus.publish(LatencySample(stage="tts", ms=320.0 + i, ts=float(i)))
        # Pump pilot long enough for the screen worker to drain
        for _ in range(5):
            await pilot.pause()
        meter = app.screen.query_one("#meter")
        latency = app.screen.query_one("#latency")
        print(f"meter rms: {getattr(meter, 'rms', '?')}")
        print(f"latency snapshot: {latency.snapshot()}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
