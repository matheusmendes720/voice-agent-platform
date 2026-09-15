"""Tuning mode placeholder — wired in Task 11."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from textual.screen import Screen
from textual.widgets import Static

if TYPE_CHECKING:
    from ..bus import EventBus


class TuningScreen(Screen):
    """Tuning mode placeholder."""

    BINDINGS = [
        ("3", "app.switch_mode('tuning')", "Tuning"),
    ]

    def __init__(self, bus: "EventBus | None" = None, voice: Any = None) -> None:
        super().__init__()
        self.bus = bus
        self.voice = voice

    def compose(self) -> None:
        yield Static("Tuning (TODO)", id="placeholder")
