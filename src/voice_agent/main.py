"""CLI entry point for voice-agent."""
from __future__ import annotations
import argparse
import asyncio
import sys
from .config import VoiceAgentConfig
from .events.bus import EventBus
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


async def _run_cli(config: VoiceAgentConfig) -> int:
    """Rich-based interactive REPL — primary user-facing mode."""
    from .cli import run_cli
    return await run_cli(config)


async def main() -> int:
    parser = argparse.ArgumentParser(prog="voice-agent")
    parser.add_argument("--headless", action="store_true", help="run without UI")
    parser.add_argument("--cli", action="store_true", help="run Rich interactive CLI (default)")
    parser.add_argument("--config", default="config/voice.toml", help="path to voice.toml")
    args = parser.parse_args()

    config = VoiceAgentConfig.from_toml(args.config)
    if args.headless:
        return await _run_headless(config)
    return await _run_cli(config)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
