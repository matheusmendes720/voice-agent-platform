"""CLI entry point for voice-agent."""
from __future__ import annotations
import asyncio
import sys
from .config import VoiceAgentConfig
from .voice.voicestudio import VoiceStudioClient
from .agent.core import VoiceAgent


async def main() -> int:
    """Main entry point."""
    config = VoiceAgentConfig.from_toml("config/voice.toml")

    vs = VoiceStudioClient(config.voicestudio.url)
    if not vs.is_available():
        print("ERROR: VoiceStudio not available at", config.voicestudio.url)
        print("Start VoiceStudio or update config/voice.toml")
        return 1

    print(f"Voice-Agent starting...")
    print(f"  VoiceStudio: {config.voicestudio.url}")
    print(f"  Voice: {config.voicestudio.default_voice}")
    print(f"  LLM: {config.llm.provider}/{config.llm.model}")

    agent_instance = VoiceAgent(config)
    try:
        await agent_instance.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        agent_instance.stop()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
