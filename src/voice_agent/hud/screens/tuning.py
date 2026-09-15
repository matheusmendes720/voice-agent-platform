"""Tuning mode — sliders + re-speak button."""
from __future__ import annotations
from typing import TYPE_CHECKING
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Input, Label

if TYPE_CHECKING:
    from ..bus import EventBus


SAMPLE_SENTENCE = "Olá! Eu sou o seu agente de voz. Como posso ajudar?"


class TuningScreen(Screen):
    BINDINGS = [
        ("3", "app.switch_mode('tuning')", "Tuning"),
        ("r", "respeak", "Re-speak"),
    ]

    def __init__(self, bus: "EventBus | None" = None) -> None:
        super().__init__()
        self.bus = bus

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("Voice tuning bench", id="title")
            with Horizontal():
                yield Label("voice")
                yield Input(value="alloy", id="voice-input", placeholder="alloy | onyx | nova | <profile-id>")
            with Horizontal():
                yield Label("speed")
                yield Input(value="1.0", id="speed-input", placeholder="0.5 - 2.0")
            with Horizontal():
                yield Label("instruct")
                yield Input(value="portuguese accent, calm", id="instruct-input")
            with Horizontal():
                yield Label("guidance")
                yield Input(value="5.0", id="guidance-input", placeholder="0.0 - 20.0")
            yield Button("Re-speak (r)", id="respeak")
            yield Static("(no preview yet)", id="preview-status")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "respeak":
            self.run_worker(self._do_respeak, exclusive=False)

    async def action_respeak(self) -> None:
        await self._do_respeak()

    async def _do_respeak(self) -> None:
        voice = getattr(self.app, "voice", None)
        if voice is None:
            self.query_one("#preview-status", Static).update("(voice client not wired)")
            return
        voice_id = self.query_one("#voice-input", Input).value or "alloy"
        try:
            speed = float(self.query_one("#speed-input", Input).value or "1.0")
        except ValueError:
            speed = 1.0
        instruct = self.query_one("#instruct-input", Input).value or None
        try:
            guidance_raw = self.query_one("#guidance-input", Input).value
            guidance = float(guidance_raw) if guidance_raw else None
        except ValueError:
            guidance = None
        self.query_one("#preview-status", Static).update("(synthesising...)")
        try:
            voice.synthesize(
                SAMPLE_SENTENCE,
                profile_id=voice_id,
                speed=speed,
                instruct=instruct,
                guidance_scale=guidance,
            )
            self.query_one("#preview-status", Static).update("(done)")
        except Exception as e:  # noqa: BLE001
            self.query_one("#preview-status", Static).update(f"(error: {e})")
