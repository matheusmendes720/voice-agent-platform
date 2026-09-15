"""RMS mic-level meter."""
from __future__ import annotations
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class MeterWidget(Static):
    """Horizontal bar showing RMS mic level (0.0–1.0)."""

    DEFAULT_CSS = """
    MeterWidget {
        height: 1;
        padding: 0 1;
        background: $boost;
    }
    """

    rms: reactive[float] = reactive(0.0)

    def _clamp(self, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    def _render_bar(self, rms: float, width: int = 32) -> str:
        n = int(self._clamp(rms) * width)
        return "█" * n + "░" * (width - n)

    def render(self) -> Text:
        return Text(self._render_bar(self.rms), style="bold green")

    def update_rms(self, value: float) -> None:
        self.rms = self._clamp(value)
