"""Live RMS waveform widget."""
from __future__ import annotations
from collections import deque
from textual.widgets import Static


class WaveformWidget(Static):
    DEFAULT_CSS = """
    WaveformWidget {
        height: 1fr;
        border: solid $secondary;
    }
    """

    def __init__(self, *, window: int = 200, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._buffer: deque[float] = deque(maxlen=window)

    def push_rms(self, value: float) -> None:
        self._buffer.append(float(value))
        self.update(self._render_str())

    def _render_str(self) -> str:
        if not self._buffer:
            return "(waveform waiting for audio...)"
        bar_chars = "▁▂▃▄▅▆▇█"
        max_w = 80
        sample = list(self._buffer)[-max_w:]
        if not sample:
            return "(empty)"
        peak = max(sample) or 1.0
        out = []
        for v in sample:
            idx = min(len(bar_chars) - 1, int((v / peak) * (len(bar_chars) - 1)))
            out.append(bar_chars[idx])
        return f"[bold cyan]{''.join(out)}[/bold cyan]"

    def on_mount(self) -> None:
        self.update(self._render_str())
