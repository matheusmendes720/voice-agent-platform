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
    agent = VoiceAgent(
        config,
        bus=bus,
        voice=vs,
        pipeline=AudioPipeline(bus=bus, sample_rate=config.audio.sample_rate),
    )
    print("headless mode — bus subscribers: 0 — ctrl-c to stop", file=sys.stderr)
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
    agent = VoiceAgent(
        config,
        bus=bus,
        voice=vs,
        pipeline=AudioPipeline(bus=bus, sample_rate=config.audio.sample_rate),
    )
    await run_hud(agent, bus, voice=vs)
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
