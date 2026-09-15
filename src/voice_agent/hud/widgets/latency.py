"""Per-stage latency badges."""
from __future__ import annotations
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

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._values: dict[str, float] = {}

    def set_stage(self, stage: str, ms: float) -> None:
        """Data-layer API: store a latency sample."""
        self._values[stage] = float(ms)
        self.update(self._render_str())

    def snapshot(self) -> dict[str, float]:
        return dict(self._values)

    def _render_str(self) -> str:
        parts = []
        for stage in self.STAGES:
            if stage in self._values:
                parts.append(f"{stage}:{self._values[stage]:.0f}ms")
        text = "  ".join(parts) if parts else "(no latency yet)"
        return f"[bold yellow]{text}[/bold yellow]"

    def on_mount(self) -> None:
        self.update(self._render_str())
