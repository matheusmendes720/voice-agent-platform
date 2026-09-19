"""Core voice agent loop."""
from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING, Any

from ..events.events import LLMToken, LLMComplete, Error
from ..config import VoiceAgentConfig
from .state import AgentState

if TYPE_CHECKING:
    from ..events.bus import EventBus
    from ..voice.pipeline import AudioPipeline
    from ..voice.voicestudio import VoiceStudioClient


async def _call_llm_streaming(prompt: str, publish):
    """Placeholder streaming LLM — emits one LLMToken per word, then LLMComplete.

    Replace _call_llm_streaming with a real MiniMax streaming chat call when
    API key + streaming endpoint are wired. The publish callback emits events
    onto the EventBus.
    """
    reply = f"(echo) {prompt}"
    for word in reply.split(" "):
        await asyncio.sleep(0.02)
        publish(LLMToken(token=word + " ", ts=time.monotonic()))
    publish(LLMComplete(text=reply, ts=time.monotonic()))


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
        """One conversation turn: stream LLM tokens, then emit LLMComplete."""
        tokens: list[str] = []

        def _emit_tok(ev) -> None:
            if isinstance(ev, LLMToken):
                tokens.append(ev.token)
            self._publish(ev)

        try:
            await _call_llm_streaming(user_text, _emit_tok)
        except Exception as e:  # noqa: BLE001 — surface to HUD
            self._publish(Error(message=str(e), source="llm", ts=time.monotonic()))
            return ""
        reply = "".join(tokens).strip()
        return reply

    async def run(self) -> None:
        """Main agent loop (placeholder — reads chunks when pipeline is set)."""
        self._running = True
        while self._running:
            await asyncio.sleep(0.1)

    def stop(self) -> None:
        self._running = False


async def _call_llm(prompt: str) -> str:
    """Backwards-compat wrapper: collect tokens from a streaming call."""
    tokens: list[str] = []

    def _capture(ev) -> None:
        if isinstance(ev, LLMToken):
            tokens.append(ev.token)

    await _call_llm_streaming(prompt, _capture)
    return "".join(tokens).strip()


__all__ = ["VoiceAgent", "VoiceAgentConfig", "_call_llm", "_call_llm_streaming"]
