"""Probe whether on_mount fires and the subscription is wired."""
import asyncio
import sys

sys.path.insert(0, r"C:\Users\mathe\code_space\voice-agent\src")

from voice_agent.config import VoiceAgentConfig
from voice_agent.hud.bus import EventBus
from voice_agent.hud.events import MicLevel
from voice_agent.agent.core import VoiceAgent
from voice_agent.voice.voicestudio import VoiceStudioClient
from voice_agent.voice.pipeline import AudioPipeline
from voice_agent.hud.app import VoiceAgentApp
from voice_agent.hud.screens.conversation import ConversationScreen


async def main() -> int:
    cfg = VoiceAgentConfig()
    bus = EventBus()
    vs = VoiceStudioClient(bus=bus)
    agent = VoiceAgent(cfg, bus=bus, voice=vs, pipeline=AudioPipeline(bus=bus))

    # Monkey-patch the screen to log lifecycle.
    orig_mount = ConversationScreen.on_mount
    async def traced_mount(self):
        print(f"[trace] ConversationScreen.on_mount fired, bus={self.bus}")
        await orig_mount(self)
        print(f"[trace] after orig_mount, sub={self._sub is not None}, pump={self._pump is not None}")
    ConversationScreen.on_mount = traced_mount

    app = VoiceAgentApp(agent, bus, voice=vs)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        print(f"screen type: {type(app.screen).__name__}")
        for i in range(3):
            bus.publish(MicLevel(rms=0.5, ts=float(i)))
        for _ in range(5):
            await pilot.pause()
        meter = app.screen.query_one("#meter")
        print(f"meter rms: {getattr(meter, 'rms', '?')}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
