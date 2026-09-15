"""Scrolling transcript widget."""
from __future__ import annotations
from rich.text import Text
from textual.widgets import Static


class TranscriptWidget(Static):
    DEFAULT_CSS = """
    TranscriptWidget {
        height: 1fr;
        padding: 0 1;
        border: solid $primary;
    }
    """

    def __init__(self, max_lines: int = 200) -> None:
        super().__init__()
        self._lines: list[str] = []
        self._max = max_lines

    def append(self, role: str, text: str) -> None:
        self._lines.append(f"{role}: {text}")
        if len(self._lines) > self._max:
            self._lines = self._lines[-self._max :]
        self.refresh()

    def render(self) -> Text:
        return Text("\n".join(self._lines) or "(no transcript yet)")
