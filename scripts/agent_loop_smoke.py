"""Loop-level smoke: TTS -> ASR -> LLM -> TTS round-trip (no mic).

Usage: python scripts/agent_loop_smoke.py
"""
from __future__ import annotations
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from voice_agent.config import VoiceAgentConfig
from voice_agent.events.bus import EventBus
from voice_agent.voice.voicestudio import VoiceStudioClient
from voice_agent.voice.pipeline import AudioPipeline
from voice_agent.agent.core import VoiceAgent


async def main() -> int:
    cfg = VoiceAgentConfig.from_toml(ROOT / "config" / "voice.toml")
    bus = EventBus()
    vs = VoiceStudioClient(cfg.voicestudio.url, bus=bus)
    if not vs.is_available():
        print("VoiceStudio not reachable")
        return 1
    pipeline = AudioPipeline(
        sample_rate=cfg.audio.sample_rate,
        bus=bus,
    )
    agent = VoiceAgent(cfg, bus=bus, voice=vs, pipeline=pipeline)

    user_text = "Olá, como você está hoje?"
    print(f"user: {user_text!r}")

    # 1) Synthesize what the user would have said (instead of mic capture)
    t0 = time.monotonic()
    synth = vs.synthesize(user_text, profile_id="alloy")
    print(f"TTS (user voice): {len(synth.audio_bytes):,} bytes  {(time.monotonic()-t0)*1000:.0f}ms")

    # 2) ASR on that audio
    t0 = time.monotonic()
    asr = vs.transcribe(synth.audio_bytes, sample_rate=24000)
    print(f"ASR: {(time.monotonic()-t0)*1000:.0f}ms -> {asr.text!r}")

    # 3) Stream the LLM reply
    t0 = time.monotonic()
    reply = await agent._turn(asr.text)
    print(f"LLM: {(time.monotonic()-t0)*1000:.0f}ms -> {reply!r}")

    # 4) TTS the reply
    if reply:
        t0 = time.monotonic()
        reply_synth = vs.synthesize(reply, profile_id=cfg.voicestudio.default_voice)
        print(f"TTS (reply): {len(reply_synth.audio_bytes):,} bytes  {(time.monotonic()-t0)*1000:.0f}ms")

    await bus.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
