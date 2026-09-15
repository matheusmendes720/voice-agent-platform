"""Waveform mode placeholder — wired to widgets in Task 10."""
from __future__ import annotations
from typing import TYPE_CHECKING
from textual.screen import Screen
from textual.widgets import Static

if TYPE_CHECKING:
    from ..bus import EventBus


class WaveformScreen(Screen):
    """Waveform mode placeholder."""

    BINDINGS = [
        ("2", "app.switch_mode('waveform')", "Waveform"),
    ]

    def __init__(self, bus: "EventBus | None" = None) -> None:
        super().__init__()
        self.bus = bus

    def compose(self) -> None:
        yield Static("Waveform (TODO)", id="placeholder")
