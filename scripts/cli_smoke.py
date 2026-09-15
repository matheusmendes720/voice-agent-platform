"""Smoke-test the Rich CLI: feed canned input, verify output."""
import asyncio
import sys
import io
import os

sys.path.insert(0, r"C:\Users\mathe\code_space\voice-agent\src")
from voice_agent.config import VoiceAgentConfig
from voice_agent.cli import RichCLI


async def main() -> int:
    cfg = VoiceAgentConfig()
    cli = RichCLI(cfg)

    # Replace stdin with a piped string of commands.
    input_script = "/status\nolá agente, como vai?\n/voice nova\n/say teste de síntese real\n/quit\n"
    sys.stdin = io.StringIO(input_script)

    # Run WITHOUT mocking — hit real VoiceStudio.
    code = await cli.run()
    print(f"exit={code}")
    return code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
