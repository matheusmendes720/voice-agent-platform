"""Core voice agent loop."""
from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING, Any

from ..hud.events import LLMComplete, Error
from ..config import VoiceAgentConfig
from .state import AgentState

if TYPE_CHECKING:
    from ..hud.bus import EventBus
    from ..voice.pipeline import AudioPipeline
    from ..voice.voicestudio import VoiceStudioClient


async def _call_llm(prompt: str) -> str:
    """Placeholder LLM call — to be replaced with MiniMax integration."""
    await asyncio.sleep(0.01)
    return f"(echo) {prompt}"


class VoiceAgent:
    """Voice agent loop, decoupled from TUI via EventBus."""

    def __init__(
        self,
        config: VoiceAgentConfig,
        bus: "EventBus | None" = None,
        pipeline: "AudioPipeline | None" = None,
        voice: "VoiceStudioClient | None" = None,
    ) -> None:
        if not isinstance(config, VoiceAgentConfig):
            raise TypeError(f"expected VoiceAgentConfig, got {type(config).__name__}")
        self.config = config
        self.bus = bus
        self.pipeline = pipeline
        self.voice = voice
        self.state = AgentState(bus=bus)
        self._running = False

    def _publish(self, event: Any) -> None:
        if self.bus is not None:
            self.bus.publish(event)

    async def _turn(self, user_text: str) -> str:
        """One conversation turn (think only; TTS happens at speak node)."""
        try:
            reply = await _call_llm(user_text)
        except Exception as e:  # noqa: BLE001 — surface to HUD
            self._publish(Error(message=str(e), source="llm", ts=time.monotonic()))
            return ""
        self._publish(LLMComplete(text=reply, ts=time.monotonic()))
        return reply

    async def run(self) -> None:
        """Main agent loop (placeholder — reads chunks when pipeline is set)."""
        self._running = True
        while self._running:
            await asyncio.sleep(0.1)

    def stop(self) -> None:
        self._running = False


__all__ = ["VoiceAgent", "VoiceAgentConfig", "_call_llm"]
