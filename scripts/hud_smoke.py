"""Drive the HUD with synthetic events, capture per-screen SVG screenshots after data has flowed."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/src")

from voice_agent.config import VoiceAgentConfig
from voice_agent.hud.bus import EventBus
from voice_agent.voice.voicestudio import VoiceStudioClient
from voice_agent.voice.pipeline import AudioPipeline
from voice_agent.agent.core import VoiceAgent
from voice_agent.hud.events import MicLevel, LatencySample, TranscriptFinal, LLMComplete


async def synthetic_pump(bus: EventBus, n: int = 30) -> None:
    """Emit a deterministic synthetic event stream for `n` ticks."""
    for i in range(n):
        bus.publish(MicLevel(rms=min(1.0, 0.1 + i * 0.03), ts=float(i)))
        if i % 4 == 0:
            bus.publish(LatencySample(stage="tts", ms=320.0 + i * 5, ts=float(i)))
            bus.publish(LatencySample(stage="asr", ms=180.0 + i * 3, ts=float(i)))
        if i % 5 == 0:
            bus.publish(TranscriptFinal(text=f"olá usuário {i}", language="pt", ts=float(i)))
        if i % 7 == 0:
            bus.publish(LLMComplete(text=f"resposta do agente {i}", ts=float(i)))
        await asyncio.sleep(0.05)


async def run() -> int:
    cfg = VoiceAgentConfig()
    bus = EventBus()
    vs = VoiceStudioClient(bus=bus)
    if not vs.is_available():
        print("VoiceStudio not available", file=sys.stderr)
        return 2
    agent = VoiceAgent(
        cfg, bus=bus, voice=vs,
        pipeline=AudioPipeline(bus=bus, sample_rate=cfg.audio.sample_rate),
    )

    from voice_agent.hud.app import VoiceAgentApp
    app = VoiceAgentApp(agent, bus, voice=vs)

    out_dir = os.path.dirname(os.path.abspath(__file__))
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        # Pump events ON the conversation screen first
        await synthetic_pump(bus, n=15)
        await pilot.pause()
        await pilot.pause()
        svg = app.export_screenshot(title="voice-agent HUD — conversation")
        p = os.path.join(out_dir, "screenshot_conversation.svg")
        open(p, "w", encoding="utf-8").write(svg)
        print(f"conversation: {len(svg)} bytes")

        # Switch to waveform
        await app.action_go_waveform()
        await pilot.pause()
        await synthetic_pump(bus, n=40)  # push more RMS samples
        await pilot.pause()
        svg = app.export_screenshot(title="voice-agent HUD — waveform")
        p = os.path.join(out_dir, "screenshot_waveform.svg")
        open(p, "w", encoding="utf-8").write(svg)
        print(f"waveform: {len(svg)} bytes")

        # Switch to tuning
        await app.action_go_tuning()
        await pilot.pause()
        await pilot.pause()
        svg = app.export_screenshot(title="voice-agent HUD — tuning")
        p = os.path.join(out_dir, "screenshot_tuning.svg")
        open(p, "w", encoding="utf-8").write(svg)
        print(f"tuning: {len(svg)} bytes")

    print("all 3 screens captured with live data")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
