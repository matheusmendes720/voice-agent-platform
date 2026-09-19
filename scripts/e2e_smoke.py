"""End-to-end smoke test against a live VoiceStudio server.

Usage: python scripts/e2e_smoke.py
"""
from __future__ import annotations
import asyncio
import json
import time
from pathlib import Path
import sys

# Allow running from project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from voice_agent.config import VoiceAgentConfig
from voice_agent.events.bus import EventBus
from voice_agent.voice.voicestudio import VoiceStudioClient


async def main() -> int:
    cfg = VoiceAgentConfig.from_toml(ROOT / "config" / "voice.toml")
    bus = EventBus()
    vs = VoiceStudioClient(cfg.voicestudio.url, bus=bus)

    if not vs.is_available():
        print("VoiceStudio: NOT REACHABLE at", cfg.voicestudio.url)
        print("  Start it or update config/voice.toml")
        return 1

    print(f"VoiceStudio: ready  url={cfg.voicestudio.url}")

    print("\n--- TTS roundtrip ---")
    sub1 = bus.subscribe()
    sample = "Olá! Teste end-to-end do voice-agent platform."
    t0 = time.monotonic()
    result = vs.synthesize(sample, profile_id="alloy")
    tts_ms = (time.monotonic() - t0) * 1000
    print(f"  in : {sample!r}")
    print(f"  out: {len(result.audio_bytes):,} bytes  in {tts_ms:,.0f}ms")

    print("\n--- ASR roundtrip (TTS output -> ASR) ---")
    t0 = time.monotonic()
    transcript = vs.transcribe(result.audio_bytes, sample_rate=24000)
    asr_ms = (time.monotonic() - t0) * 1000
    print(f"  text: {transcript.text!r}")
    print(f"  latency: {asr_ms:,.0f}ms")

    print("\n--- Drain bus events ---")
    drained = []
    while True:
        try:
            ev = await asyncio.wait_for(sub1.next(), timeout=0.2)
            drained.append(type(ev).__name__)
        except (asyncio.TimeoutError, StopAsyncIteration):
            break
    counts: dict[str, int] = {}
    for name in drained:
        counts[name] = counts.get(name, 0) + 1
    print("  events:", json.dumps(counts, indent=2))

    await bus.close()
    total = tts_ms + asr_ms
    print(f"\nTotal E2E: {total:,.0f}ms")
    return 0 if transcript.text.strip() else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
