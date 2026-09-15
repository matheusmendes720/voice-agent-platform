"""Textual App for voice-agent HUD."""
from __future__ import annotations
import asyncio
from typing import Any

from textual.app import App
from textual.binding import Binding

from .bus import EventBus
from .screens.conversation import ConversationScreen
from .screens.waveform import WaveformScreen
from .screens.tuning import TuningScreen


class VoiceAgentApp(App):
    """Three-mode HUD: Conversation / Waveform / Tuning."""

    TITLE = "voice-agent"
    SUB_TITLE = "TTS · ASR · LLM"

    BINDINGS = [
        Binding("tab", "next_mode", "Next mode"),
        Binding("shift+tab", "prev_mode", "Prev mode"),
        Binding("1", "go_conversation", "Conversation"),
        Binding("2", "go_waveform", "Waveform"),
        Binding("3", "go_tuning", "Tuning"),
        Binding("q", "quit", "Quit"),
    ]

    MODES = {
        "conversation": ConversationScreen,
        "waveform": WaveformScreen,
        "tuning": TuningScreen,
    }

    def __init__(self, agent: Any, bus: EventBus, voice: Any = None) -> None:
        super().__init__()
        self.agent = agent
        self.bus = bus
        self.voice = voice
        self._mode_index = 0

    def on_mount(self) -> None:
        self.switch_mode("conversation")
        self._pump_task: asyncio.Task[None] = asyncio.create_task(self._pump_events())

    async def _pump_events(self) -> None:
        sub = self.bus.subscribe()
        try:
            async for ev in sub:
                # Phase 1: ignore payload; widgets will subscribe later.
                self.log(f"event: {type(ev).__name__}")
        except Exception:
            pass

    async def action_next_mode(self) -> None:
        keys = list(self.MODES.keys())
        self._mode_index = (self._mode_index + 1) % len(keys)
        self.switch_mode(keys[self._mode_index])

    async def action_prev_mode(self) -> None:
        keys = list(self.MODES.keys())
        self._mode_index = (self._mode_index - 1) % len(keys)
        self.switch_mode(keys[self._mode_index])

    async def action_go_conversation(self) -> None:
        self.switch_mode("conversation")

    async def action_go_waveform(self) -> None:
        self.switch_mode("waveform")

    async def action_go_tuning(self) -> None:
        self.switch_mode("tuning")


def build_app(agent: Any, bus: EventBus, voice: Any = None) -> VoiceAgentApp:
    return VoiceAgentApp(agent, bus, voice=voice)


async def run_hud(agent: Any, bus: EventBus, voice: Any = None) -> None:
    app = build_app(agent, bus, voice=voice)
    await app.run_async()
