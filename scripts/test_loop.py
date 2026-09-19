"""Test the FULL VoiceAgent.run() loop end-to-end without a real mic.

Substitutes mic capture with a synthesized audio buffer so we can verify
the wiring (mic → ASR → LLM → TTS → speaker) all the way through.
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
from voice_agent.events.events import (
    MicLevel, TranscriptFinal, LLMComplete, LLMToken,
    AudioOutputStart, AudioOutputEnd, Error as ErrorEvent, LatencySample,
)
from voice_agent.voice.voicestudio import VoiceStudioClient
from voice_agent.voice.pipeline import AudioPipeline
from voice_agent.agent.core import VoiceAgent


class FakePipeline:
    """Drop-in for AudioPipeline — pretends to capture audio that was
    previously synthesized. Feels like a real mic from the agent's POV."""

    def __init__(self, real_pipeline: AudioPipeline, fake_pcm: bytes):
        self._real = real_pipeline
        self._fake_pcm = fake_pcm
        self.sample_rate = real_pipeline.sample_rate
        self.bus = real_pipeline.bus

    def record_utterance(self, **kwargs) -> bytes:
        # publish a fake mic level for the HUD
        if self.bus:
            from voice_agent.events.events import MicLevel, AudioChunk
            import time as _t
            self.bus.publish(MicLevel(rms=0.5, ts=_t.monotonic()))
            self.bus.publish(AudioChunk(data=self._fake_pcm, sample_rate=self.sample_rate, ts=_t.monotonic()))
        return self._fake_pcm

    def play(self, *args, **kwargs):
        return self._real.play(*args, **kwargs)

    def close(self):
        self._real.close()


async def main() -> int:
    cfg = VoiceAgentConfig.from_toml(ROOT / "config" / "voice.toml")
    bus = EventBus()
    vs = VoiceStudioClient(cfg.voicestudio.url, bus=bus)
    if not vs.is_available():
        print("VoiceStudio not reachable")
        return 1

    real_pipeline = AudioPipeline(sample_rate=cfg.audio.sample_rate, bus=bus)

    # Substitutes mic — synthesize a user prompt first
    user_prompt = "Olá, como você está?"
    print(f"[setup] synthesizing user prompt: {user_prompt!r}")
    synth_user = vs.synthesize(user_prompt, profile_id="alloy")
    # strip WAV header so ASR sees raw PCM
    pcm = (
        synth_user.audio_bytes[44:]
        if synth_user.audio_bytes[:4] == b"RIFF"
        else synth_user.audio_bytes
    )
    print(f"[setup] {len(pcm):,} bytes of PCM ready")

    pipeline = FakePipeline(real_pipeline, pcm)
    agent = VoiceAgent(cfg, bus=bus, voice=vs, pipeline=pipeline)

    # Subscribe to bus events for visibility
    sub = bus.subscribe()

    async def drain_and_print():
        while True:
            try:
                ev = await asyncio.wait_for(sub.next(), timeout=60.0)
            except asyncio.TimeoutError:
                print("[bus] timeout — no more events")
                break
            if isinstance(ev, MicLevel):
                print(f"[bus] MicLevel rms={ev.rms:.2f}")
            elif isinstance(ev, TranscriptFinal):
                print(f"[bus] TranscriptFinal: {ev.text!r}")
            elif isinstance(ev, LLMToken):
                sys.stdout.write(ev.token)
                sys.stdout.flush()
            elif isinstance(ev, LLMComplete):
                print()
                print(f"[bus] LLMComplete: {ev.text!r}")
            elif isinstance(ev, LatencySample):
                print(f"[bus] Latency [{ev.stage}] {ev.ms:.0f} ms")
            elif isinstance(ev, AudioOutputStart):
                print(f"[bus] AudioOutputStart")
            elif isinstance(ev, AudioOutputEnd):
                print(f"[bus] AudioOutputEnd duration={ev.duration_ms} ms")
            elif isinstance(ev, ErrorEvent):
                print(f"[bus] ERROR ({ev.source}): {ev.message}")

    printer = asyncio.create_task(drain_and_print())

    # Run agent for one turn then stop
    print()
    print("[run] starting agent.run() — one turn then stop...")
    runner = asyncio.create_task(agent.run())
    # Wait until we see LLMComplete, then give it a moment to finish speaking
    saw_complete = asyncio.Event()
    def _on(ev):
        if isinstance(ev, LLMComplete):
            saw_complete.set()
    sink = bus.subscribe()
    async def wait_for_complete():
        async for ev in sink:
            _on(ev)
            if saw_complete.is_set():
                # give TTS play another 5s
                await asyncio.sleep(5)
                break
    waiter = asyncio.create_task(wait_for_complete())
    await waiter
    agent.stop()
    await asyncio.wait_for(runner, timeout=10.0)
    printer.cancel()
    bus.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
