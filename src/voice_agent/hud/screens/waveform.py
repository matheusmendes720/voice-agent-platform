"""Waveform mode — live RMS plot."""
from __future__ import annotations
from typing import TYPE_CHECKING
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer
from ..widgets.waveform import WaveformWidget

if TYPE_CHECKING:
    from ..bus import EventBus


class WaveformScreen(Screen):
    BINDINGS = [
        ("2", "app.switch_mode('waveform')", "Waveform"),
    ]

    def __init__(self, bus: "EventBus | None" = None) -> None:
        super().__init__()
        self.bus = bus
        self._sub = None
        self._pump = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield WaveformWidget(id="waveform")
        yield Footer()

    async def on_mount(self) -> None:
        if self.bus is None:
            return
        self._sub = self.bus.subscribe()
        self._pump = self._pump_events()
        self.run_worker(self._pump, exclusive=True)

    async def _pump_events(self) -> None:
        from ..events import MicLevel
        if self._sub is None:
            return
        async for ev in self._sub:
            if isinstance(ev, MicLevel):
                try:
                    w = self.query_one("#waveform", WaveformWidget)
                except Exception:
                    continue
                w.push_rms(ev.rms)
                self.refresh()
