"""Core voice agent loop."""
from __future__ import annotations
import asyncio
from .state import AgentState


class VoiceAgent:
    """Basic voice agent loop.

    Takes the full VoiceAgentConfig from ..config so that sub-components
    (voicestudio, llm, audio, agent) are all accessible.
    """

    def __init__(self, config: "VoiceAgentConfig") -> None:
        from ..config import VoiceAgentConfig as VAC
        if not isinstance(config, VAC):
            raise TypeError(f"expected VoiceAgentConfig, got {type(config).__name__}")
        self.config = config
        self.state = AgentState()
        self._running = False

    async def run(self) -> None:
        """Main agent loop (placeholder - hooks to pipeline + graph)."""
        self._running = True
        while self._running:
            await asyncio.sleep(0.1)

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False


# Re-export so callers can import from one place
from ..config import VoiceAgentConfig as VoiceAgentConfig
__all__ = ["VoiceAgent", "VoiceAgentConfig"]
