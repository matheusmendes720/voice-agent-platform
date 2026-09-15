"""Per-stage latency badges."""
from __future__ import annotations
from rich.text import Text
from textual.widgets import Static


class LatencyWidget(Static):
    DEFAULT_CSS = """
    LatencyWidget {
        height: 1;
        padding: 0 1;
        background: $panel;
    }
    """

    STAGES = ("asr", "llm", "tts", "playback")

    def __init__(self) -> None:
        super().__init__()
        self._values: dict[str, float] = {}

    def update(self, stage: str, ms: float) -> None:
        self._values[stage] = float(ms)
        self.refresh()

    def snapshot(self) -> dict[str, float]:
        return dict(self._values)

    def _render(self) -> str:
        parts = []
        for stage in self.STAGES:
            if stage in self._values:
                parts.append(f"{stage}:{self._values[stage]:.0f}ms")
        return "  ".join(parts) if parts else "(no latency yet)"

    def render(self) -> Text:
        return Text(self._render(), style="bold yellow")
