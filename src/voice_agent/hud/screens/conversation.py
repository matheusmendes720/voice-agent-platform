"""Conversation mode — mic meter + transcript + latency badges."""
from __future__ import annotations
from typing import TYPE_CHECKING
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer
from ..widgets.meter import MeterWidget
from ..widgets.transcript import TranscriptWidget
from ..widgets.latency import LatencyWidget

if TYPE_CHECKING:
    from ..bus import EventBus


class ConversationScreen(Screen):
    BINDINGS = [
        ("1", "app.switch_mode('conversation')", "Conversation"),
        ("m", "mute", "Mute"),
    ]

    def __init__(self, bus: "EventBus | None" = None) -> None:
        super().__init__()
        self.bus = bus
        self._sub = None
        self._pump = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield LatencyWidget(id="latency")
            yield MeterWidget(id="meter")
            yield TranscriptWidget(id="transcript")
        yield Footer()

    async def on_mount(self) -> None:
        if self.bus is None:
            app_bus = getattr(self.app, "bus", None)
            if app_bus is not None:
                self.bus = app_bus
        if self.bus is None:
            return
        self._sub = self.bus.subscribe()
        self._pump = self._pump_events()
        self.run_worker(self._pump, exclusive=True, thread=False)

    async def _pump_events(self) -> None:
        from ..events import MicLevel, TranscriptFinal, LatencySample
        if self._sub is None:
            return
        async for ev in self._sub:
            try:
                meter = self.query_one("#meter", MeterWidget)
                latency = self.query_one("#latency", LatencyWidget)
                transcript = self.query_one("#transcript", TranscriptWidget)
            except Exception:
                # screen not mounted yet or already unmounted
                continue
            if isinstance(ev, MicLevel):
                meter.update_rms(ev.rms)
            elif isinstance(ev, LatencySample):
                latency.set_stage(ev.stage, ev.ms)
            elif isinstance(ev, TranscriptFinal):
                transcript.append("user", ev.text)
            self.refresh()

    async def action_mute(self) -> None:
        # TODO: wire to AudioPipeline.threshold or pipeline flag
        self.app.log("mute toggle requested (TODO)")
