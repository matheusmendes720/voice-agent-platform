"""Interactive CLI for voice-agent — Rich Live UI, mic always listening.

Streams mic → ASR → LLM → TTS with live progress.

Usage:
    python -m voice_agent --cli --config config/voice.toml

Slash commands (type at the prompt, then Enter):
    /voice <id>       switch TTS voice (alloy | onyx | nova | ...)
    /speed <0.5-2.0>  set TTS speed
    /instruct <text>  set TTS instruct prompt (or /instruct clear)
    /language <pt|en|...>  set recognition language
    /say <text>       synthesize & play arbitrary text
    /help             show commands
    /quit             exit
"""
from __future__ import annotations
import asyncio
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..config import VoiceAgentConfig
from ..events.bus import EventBus
from ..events.events import (
    MicLevel,
    TranscriptFinal,
    LLMToken,
    LLMComplete,
    LatencySample,
    AudioOutputStart,
    AudioOutputEnd,
    Error as ErrorEvent,
)
from ..voice.voicestudio import VoiceStudioClient
from ..voice.pipeline import AudioPipeline
from ..agent.core import VoiceAgent


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------

@dataclass
class State:
    voice: str = "alloy"
    speed: float = 1.0
    instruct: str | None = None
    status: str = "listening…"
    listening: bool = True
    last_mic_rms: float = 0.0
    last_user_text: str = ""
    last_llm_text: str = ""
    stream_buf: str = ""
    last_latency: dict[str, float] = field(default_factory=dict)
    last_tts_duration_ms: int = 0
    errors: list[str] = field(default_factory=list)
    history: deque[tuple[str, str]] = field(default_factory=lambda: deque(maxlen=4))


# ---------------------------------------------------------------------------
# rendering helpers
# ---------------------------------------------------------------------------

def _meter(rms: float, width: int = 30) -> Text:
    """Vertical-ish bar that scales an RMS 0..5000 RMS into a meter."""
    pct = max(0.0, min(1.0, rms / 2000.0))
    n = int(pct * width)
    bar = "█" * n + "░" * (width - n)
    color = "green" if pct < 0.6 else ("yellow" if pct < 0.85 else "red")
    return Text.assemble(
        ("mic ", "dim"),
        (bar, f"bold {color}"),
        (f"  rms={rms:>6.0f}", "dim"),
    )


def _header(state: State) -> Panel:
    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="center", ratio=2)
    grid.add_column(justify="right", ratio=1)

    left = Text()
    left.append("voice  ", style="dim")
    left.append(state.voice, style="bold cyan")
    left.append("    speed  ", style="dim")
    left.append(f"{state.speed:.2f}x", style="cyan")

    middle = Text(state.status, style="bold magenta", justify="center")

    latency_parts = []
    for stage in ("asr", "llm", "tts"):
        if stage in state.last_latency:
            latency_parts.append(f"{stage}={state.last_latency[stage]:.0f}ms")
    right = Text.assemble(
        ("lat  ", "dim"),
        ("  ".join(latency_parts), "yellow") if latency_parts else ("—", "dim"),
        (f"  tts={state.last_tts_duration_ms}ms", "dim"),
    )

    grid.add_row(left, middle, right)
    return Panel(grid, border_style="cyan", title="[bold]voice-agent[/bold]", title_align="left")


def _meter_panel(state: State) -> Panel:
    return Panel(_meter(state.last_mic_rms), border_style="green", title="[dim]mic[/dim]", height=3)


def _stream_panel(state: State) -> Panel:
    body = Text()
    body.append("▎ ", style="bold magenta")
    body.append(state.stream_buf or " ", style="italic")
    if state.stream_buf:
        body.append(" ▌", style="bold magenta blink")
    return Panel(
        Align.left(body, vertical="middle"),
        border_style="magenta",
        title="[dim]agent (streaming)[/dim]",
        height=5,
    )


def _history_panel(state: State) -> Panel:
    body = Text()
    if not state.history:
        body.append("(waiting for first turn)", style="dim italic")
    for who, line in state.history:
        if who == "user":
            body.append("you   ", style="bold cyan")
            body.append(line + "\n", style="cyan")
        else:
            body.append("agent ", style="bold magenta")
            body.append(line + "\n", style="magenta")
    return Panel(
        body,
        border_style="blue",
        title="[dim]conversation[/dim]",
    )


def _footer() -> Panel:
    body = Text.assemble(
        ("[voice]", "dim"),
        (" /voice <id>  ", "bold"),
        ("[speed]", "dim"),
        (" /speed <0.5-2.0>  ", "bold"),
        ("[instruct]", "dim"),
        (" /instruct <…>  ", "bold"),
        ("[lang]", "dim"),
        (" /language <…>  ", "bold"),
        ("[say]", "dim"),
        (" /say <text>  ", "bold"),
        ("[exit]", "dim"),
        (" /quit", "bold"),
    )
    return Panel(Align.center(body), border_style="grey50", height=3)


def build_layout(state: State) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="meter", size=3),
        Layout(name="stream", size=5),
        Layout(name="history", ratio=1),
        Layout(name="footer", size=3),
    )
    layout["header"].update(_header(state))
    layout["meter"].update(_meter_panel(state))
    layout["stream"].update(_stream_panel(state))
    layout["history"].update(_history_panel(state))
    layout["footer"].update(_footer())
    return layout


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class RichCLI:
    BANNER = "[bold cyan]voice-agent[/bold cyan] — [dim]listening, speak to chat[/dim]"

    def __init__(self, config: VoiceAgentConfig) -> None:
        self.config = config
        self.console = Console()
        self.bus = EventBus()
        self.state = State(voice=config.voicestudio.default_voice)
        self.vs = VoiceStudioClient(config.voicestudio.url, bus=self.bus)
        self.pipeline = AudioPipeline(
            bus=self.bus,
            sample_rate=config.audio.sample_rate,
            threshold=config.audio.silence_threshold,
            input_device=config.audio.input_device,
        )
        self.agent = VoiceAgent(config, bus=self.bus, voice=self.vs, pipeline=self.pipeline)
        self._stopped = False

    # ---- bus subscriber that mutates state -------------------------------

    async def _pump_events(self) -> None:
        sub = self.bus.subscribe()
        try:
            async for ev in sub:
                if isinstance(ev, MicLevel):
                    self.state.last_mic_rms = ev.rms
                elif isinstance(ev, TranscriptFinal):
                    text = (ev.text or "").strip()
                    if not text:
                        continue
                    # record previous exchange
                    if self.state.last_user_text and self.state.last_llm_text:
                        self.state.history.append((self.state.last_user_text, self.state.last_llm_text))
                    self.state.last_user_text = text
                    self.state.last_llm_text = ""
                    self.state.stream_buf = ""
                    self.state.status = "thinking…"
                elif isinstance(ev, LLMToken):
                    self.state.stream_buf += ev.token
                elif isinstance(ev, LLMComplete):
                    text = (ev.text or "").strip()
                    self.state.last_llm_text = text
                    self.state.stream_buf = ""
                    self.state.status = "listening…"
                elif isinstance(ev, LatencySample):
                    self.state.last_latency[ev.stage] = ev.ms
                elif isinstance(ev, AudioOutputStart):
                    self.state.status = "speaking…"
                elif isinstance(ev, AudioOutputEnd):
                    self.state.last_tts_duration_ms = ev.duration_ms
                    self.state.status = "listening…"
                elif isinstance(ev, ErrorEvent):
                    msg = f"{ev.source}: {ev.message}"
                    self.state.errors.append(msg)
                    # keep last 3 only
                    self.state.errors = self.state.errors[-3:]
                    self.state.status = f"error: {ev.source}"
        except asyncio.CancelledError:
            pass

    # ---- command REPL ----------------------------------------------------

    HELP = (
        "[bold]commands:[/bold]\n"
        "  /voice <id>      switch TTS voice (alloy | onyx | nova | …)\n"
        "  /speed <0.5-2.0> set TTS speed\n"
        "  /instruct <text> set TTS instruct prompt (or /instruct clear)\n"
        "  /language <pt|en|...>  set recognition language\n"
        "  /say <text>      synthesize & play arbitrary text\n"
        "  /quit            exit\n"
    )

    async def _repl(self, live: Live) -> None:
        loop = asyncio.get_event_loop()
        while not self._stopped:
            line = await loop.run_in_executor(None, self._readline)
            if line is None:
                return
            line = line.strip()
            if not line:
                continue
            if line.startswith("/"):
                await self._handle_command(line, live)
            else:
                await self._speak(line)

    def _readline(self) -> str | None:
        try:
            return input()
        except EOFError:
            return None

    async def _handle_command(self, line: str, live: Live) -> None:
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        with live.console.capture() as cap:
            if cmd in ("/quit", "/exit"):
                self._stopped = True
            elif cmd == "/help":
                live.console.print(self.HELP)
            elif cmd == "/voice":
                if not arg:
                    live.console.print(f"[dim]voice = {self.agent.voice_id}[/dim]")
                else:
                    self.agent.voice_id = arg
                    self.state.voice = arg
                    live.console.print(f"[green]voice → {arg} (applied to agent)[/green]")
            elif cmd == "/speed":
                try:
                    v = float(arg)
                    if 0.25 <= v <= 4.0:
                        self.state.speed = v
                        live.console.print(f"[green]speed → {v:.2f}[/green]")
                    else:
                        live.console.print("[red]speed must be in 0.25-4.0[/red]")
                except ValueError:
                    live.console.print("[red]usage: /speed <float>[/red]")
            elif cmd == "/instruct":
                self.state.instruct = None if arg.strip().lower() == "clear" else arg
                live.console.print(f"[green]instruct → {self.state.instruct or '—'}[/green]")
            elif cmd == "/language":
                live.console.print(f"[green]language → {arg or 'pt'}[/green]")
            elif cmd == "/say":
                await self._speak(arg)
            else:
                live.console.print(f"[red]unknown command: {cmd}[/red]")

    async def _speak(self, text: str) -> None:
        if not text:
            return
        try:
            self.bus.publish(LLMComplete(text=f"/say: {text}", ts=time.monotonic()))
            self.vs.synthesize(
                text,
                profile_id=self.agent.voice_id,
                speed=self.state.speed,
                instruct=self.state.instruct,
            )
        except Exception as e:  # noqa: BLE001
            self.bus.publish(ErrorEvent(message=str(e), source="tts", ts=time.monotonic()))

    # ---- main entry ------------------------------------------------------

    async def run(self) -> int:
        if not self.vs.is_available():
            self.console.print(
                f"[red]VoiceStudio not reachable at {self.config.voicestudio.url}[/red]\n"
                f"Start it or update config/voice.toml."
            )
            return 2

        self.console.print(self.BANNER)
        self.console.print(
            "[bold green]live[/bold green] — speak and watch the panels update; "
            "type /help for commands. Ctrl+C to exit."
        )

        layout = build_layout(self.state)
        pump_task = asyncio.create_task(self._pump_events())
        agent_task = asyncio.create_task(self.agent.run())

        try:
            with Live(layout, refresh_per_second=10, screen=False) as live:
                # Refresh loop on the live display — also drives the display
                try:
                    await self._repl(live)
                except (KeyboardInterrupt, asyncio.CancelledError):
                    pass
                finally:
                    # Final refresh before exit so the latest state is visible
                    live.update(build_layout(self.state))
        finally:
            self._stopped = True
            agent_task.cancel()
            pump_task.cancel()
            self.pipeline.close()
            try:
                await self.bus.close()
            except Exception:
                pass
            self.console.print("[dim]bye.[/dim]")
        return 0


async def run_cli(config: VoiceAgentConfig) -> int:
    cli = RichCLI(config)
    return await cli.run()
