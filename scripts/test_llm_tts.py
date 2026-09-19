"""LLM → TTS smoke: ask MiniMax, synthesize the reply, play it.

Usage: python scripts/test_llm_tts.py
"""
from __future__ import annotations
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from voice_agent.config import VoiceAgentConfig
from voice_agent.events.events import LLMToken, LLMComplete, Error
from voice_agent.voice.voicestudio import VoiceStudioClient
from voice_agent.voice.pipeline import AudioPipeline
from voice_agent.agent.minimax_client import MiniMaxStreamClient


async def main() -> int:
    cfg = VoiceAgentConfig.from_toml(ROOT / "config" / "voice.toml")
    vs = VoiceStudioClient(cfg.voicestudio.url)
    if not vs.is_available():
        print("VoiceStudio not reachable")
        return 1
    pipeline = AudioPipeline(sample_rate=cfg.audio.sample_rate)

    prompt = sys.argv[1] if len(sys.argv) > 1 else "me diga uma frase em português"

    print(f"prompt: {prompt!r}")
    print()

    tokens: list[str] = []
    err: list[str] = []
    completed = []

    def collect(ev) -> None:
        if isinstance(ev, LLMToken):
            tokens.append(ev.token)
            print(ev.token, end="", flush=True)
        elif isinstance(ev, LLMComplete):
            completed.append(ev)
        elif isinstance(ev, Error):
            err.append(ev.message)

    try:
        client = MiniMaxStreamClient()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 2

    print("LLM : ", end="", flush=True)
    t0 = time.monotonic()
    await client.stream(prompt, collect)
    llm_ms = (time.monotonic() - t0) * 1000
    print()
    print()

    if err:
        print(f"LLM error: {err[0][:200]}")
        return 3
    full = "".join(tokens).strip()
    if not full:
        print("LLM returned empty")
        return 4
    print(f"reply: {full!r}  ({llm_ms:.0f} ms)")
    print()

    print("TTS ...")
    t0 = time.monotonic()
    synth = vs.synthesize(full, profile_id=cfg.voicestudio.default_voice)
    tts_ms = (time.monotonic() - t0) * 1000
    print(f"  out: {len(synth.audio_bytes):,} bytes  ({tts_ms:.0f} ms)")
    print()

    out = ROOT / "scripts" / "_artifacts" / "llm_tts_reply.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(synth.audio_bytes)
    print(f"saved: {out}")
    print()

    print("play...")
    await asyncio.to_thread(pipeline.play, synth.audio_bytes, synth.sample_rate)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
