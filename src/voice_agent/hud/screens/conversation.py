"""Conversation mode placeholder — wired to widgets in Task 9."""
from __future__ import annotations
from typing import TYPE_CHECKING
from textual.screen import Screen
from textual.widgets import Static

if TYPE_CHECKING:
    from ..bus import EventBus


class ConversationScreen(Screen):
    """Conversation mode placeholder."""

    BINDINGS = [
        ("1", "app.switch_mode('conversation')", "Conversation"),
    ]

    def __init__(self, bus: "EventBus | None" = None) -> None:
        super().__init__()
        self.bus = bus

    def compose(self) -> None:
        yield Static("Conversation (TODO)", id="placeholder")
