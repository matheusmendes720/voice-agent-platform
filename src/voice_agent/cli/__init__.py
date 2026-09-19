"""Interactive Rich CLI for voice-agent — replaces the Textual HUD.

Streams mic → ASR → LLM → TTS with live progress, spinners, and slash
commands for live tuning. Keeps the EventBus as the internal event bus.

Usage:
    python -m voice_agent --cli --config config/voice.toml

Slash commands (type at the prompt, then Enter):
    /voice <id>     — switch TTS voice (e.g. /voice onyx)
    /speed <0.5-2.0> — set TTS speed
    /instruct <text> — set TTS instruct prompt
    /language <pt|en|...> — set recognition language
    /mode push-to-talk | open-mic — pick capture mode
    /status         — print last latency, voice, mic level
    /quit           — exit
"""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.align import Align
from rich import box

from ..config import VoiceAgentConfig
from ..events.bus import EventBus
from ..events.events import (
    MicLevel,
    TranscriptFinal,
    LLMComplete,
    LatencySample,
    AudioOutputStart,
    AudioOutputEnd,
    Error as ErrorEvent,
)
from ..voice.voicestudio import VoiceStudioClient
from ..voice.pipeline import AudioPipeline
from ..agent.core import VoiceAgent


@dataclass
class SessionState:
    voice_id: str = "alloy"
    speed: float = 1.0
    instruct: str | None = None
    language: str = "pt"
    mode: str = "push-to-talk"
    last_mic_rms: float = 0.0
    last_latency: dict[str, float] = field(default_factory=dict)
    last_user_text: str = ""
    last_llm_text: str = ""
    last_tts_ms: int = 0
    last_asr_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


class RichCLI:
    """Interactive Rich-based REPL."""

    BANNER = "[bold cyan]voice-agent CLI[/bold cyan] — [dim]type /help for commands[/dim]"

    def __init__(self, config: VoiceAgentConfig) -> None:
        self.config = config
        self.console = Console()
        self.bus = EventBus()
        self.state = SessionState(voice_id=config.voicestudio.default_voice)
        self.vs = VoiceStudioClient(config.voicestudio.url, bus=self.bus)
        self.pipeline = AudioPipeline(bus=self.bus, sample_rate=config.audio.sample_rate)
        self.agent = VoiceAgent(config, bus=self.bus, voice=self.vs, pipeline=self.pipeline)
        self._stopped = False

    # ---------- rendering ------------------------------------------------------

    def _status_table(self) -> Table:
        s = self.state
        grid = Table(box=box.SIMPLE, show_header=False, expand=True)
        grid.add_column(style="bold")
        grid.add_column()
        grid.add_row("voice", s.voice_id)
        grid.add_row("speed", f"{s.speed:.2f}")
        grid.add_row("instruct", s.instruct or "—")
        grid.add_row("language", s.language)
        grid.add_row("mode", s.mode)
        grid.add_row("mic", self._meter_bar(s.last_mic_rms))
        if s.last_latency:
            lat = "  ".join(f"{k}:{v:.0f}ms" for k, v in s.last_latency.items())
            grid.add_row("latency", lat)
        if s.errors:
            grid.add_row("errors", f"[red]{len(s.errors)} (last: {s.errors[-1][:40]}…)[/red]")
        grid.title = "[bold]status[/bold]"
        grid.title_justify = "left"
        return grid

    @staticmethod
    def _meter_bar(rms: float, width: int = 20) -> str:
        n = int(max(0.0, min(1.0, rms)) * width)
        return f"[bold green]{'█' * n}[/bold green][dim]{'░' * (width - n)}[/dim] {rms:.2f}"

    def _transcript_panel(self) -> Panel:
        s = self.state
        body = Text()
        if s.last_user_text:
            body.append("you: ", style="bold cyan")
            body.append(s.last_user_text + "\n")
        if s.last_llm_text:
            body.append("agent: ", style="bold magenta")
            body.append(s.last_llm_text + "\n")
        if not body.plain:
            body.append("(waiting for first turn…)\n", style="dim")
        return Panel(body, title="[bold]conversation[/bold]", border_style="cyan", box=box.ROUNDED)

    # ---------- command loop ---------------------------------------------------

    HELP_TEXT = (
        "[bold]commands:[/bold]\n"
        "  /voice <id>       switch TTS voice (alloy | onyx | nova | …)\n"
        "  /speed <0.5-2.0>  set TTS speed\n"
        "  /instruct <text>  set TTS instruct prompt (or /instruct clear)\n"
        "  /language <code>  set recognition language (pt | en | …)\n"
        "  /say <text>       type a turn instead of speaking\n"
        "  /status           print status table\n"
        "  /help             show this help\n"
        "  /quit             exit\n"
    )

    async def run(self) -> int:
        if not self.vs.is_available():
            self.console.print(
                f"[red]VoiceStudio not reachable at {self.config.voicestudio.url}[/red]\n"
                f"Start it or update config/voice.toml."
            )
            return 2

        self.console.print(self.BANNER)
        self.console.print(
            "[bold green]listening to mic[/bold green] — speak to chat. "
            "Type /help for commands. Ctrl+C to exit."
        )

        # Bus subscriber keeps state fresh + prints transcripts as they land.
        pump_task = asyncio.create_task(self._pump_events())

        # Agent loop: record_utterance → ASR → LLM → TTS → play.
        agent_task = asyncio.create_task(self.agent.run())

        # REPL on stdin — used only for /commands, NOT for normal conversation.
        try:
            await self._repl()
        finally:
            self._stopped = True
            agent_task.cancel()
            pump_task.cancel()
            self.pipeline.close()
            await self.bus.close()
            self.console.print("[dim]bye.[/dim]")
        return 0

    async def _pump_events(self) -> None:
        sub = self.bus.subscribe()
        try:
            async for ev in sub:
                if isinstance(ev, MicLevel):
                    self.state.last_mic_rms = ev.rms
                elif isinstance(ev, TranscriptFinal):
                    text = (ev.text or "").strip()
                    if not text or text == self.state.last_user_text:
                        continue
                    self.state.last_user_text = text
                    self.console.print(f"[bold cyan]you:[/bold cyan] {text}")
                elif isinstance(ev, LLMComplete):
                    text = (ev.text or "").strip()
                    if text and text != self.state.last_llm_text:
                        self.state.last_llm_text = text
                        self.console.print(f"[bold magenta]agent:[/bold magenta] {text}")
                elif isinstance(ev, LatencySample):
                    self.state.last_latency[ev.stage] = ev.ms
                    if ev.stage == "asr":
                        self.state.last_asr_ms = ev.ms
                elif isinstance(ev, AudioOutputStart):
                    self.console.print("[dim]🔊 speaking…[/dim]")
                elif isinstance(ev, AudioOutputEnd):
                    self.state.last_tts_ms = ev.duration_ms
                elif isinstance(ev, ErrorEvent):
                    self.state.errors.append(ev.message)
                    self.console.print(f"[red]error ({ev.source}):[/red] {ev.message}")
        except asyncio.CancelledError:
            pass
        except Exception as e:  # noqa: BLE001
            self.console.print(f"[red]pump died:[/red] {e}")

    async def _repl(self) -> None:
        loop = asyncio.get_event_loop()
        # Render an unobtrusive prompt that doesn't suggest typing chat input.
        self.console.print()
        while not self._stopped:
            line = await loop.run_in_executor(None, self._readline)
            if line is None:
                return
            line = line.strip()
            if not line:
                continue
            if line.startswith("/"):
                await self._handle_command(line)
            else:
                # Free-form text typed at the prompt: route it as a /say turn.
                await self._speak(line)
                self.console.print(f"[bold cyan]{self.state.voice_id}[/bold cyan] > ", end="")

    def _readline(self) -> str | None:
        try:
            return input(f"[bold cyan]{self.state.voice_id}[/bold cyan] > ")
        except EOFError:
            return None

    async def _handle_command(self, line: str) -> None:
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        if cmd == "/quit" or cmd == "/exit":
            self._stopped = True
        elif cmd == "/help":
            self.console.print(self.HELP_TEXT)
        elif cmd == "/status":
            self.console.print(self._status_table())
        elif cmd == "/voice":
            if not arg:
                self.console.print(f"[red]usage:[/red] /voice <id> (current: {self.state.voice_id})")
            else:
                self.state.voice_id = arg
                self.console.print(f"[green]voice →[/green] {arg}")
        elif cmd == "/speed":
            try:
                v = float(arg)
                assert 0.25 <= v <= 4.0
            except (ValueError, AssertionError):
                self.console.print("[red]usage:[/red] /speed 0.5-2.0")
                return
            self.state.speed = v
            self.console.print(f"[green]speed →[/green] {v:.2f}")
        elif cmd == "/instruct":
            self.state.instruct = None if arg.strip().lower() == "clear" else arg
            self.console.print(f"[green]instruct →[/green] {self.state.instruct or '—'}")
        elif cmd == "/language":
            self.state.language = arg or "pt"
            self.console.print(f"[green]language →[/green] {self.state.language}")
        elif cmd == "/mode":
            if arg not in ("push-to-talk", "open-mic"):
                self.console.print("[red]usage:[/red] /mode push-to-talk | open-mic")
            else:
                self.state.mode = arg
                self.console.print(f"[green]mode →[/green] {arg}")
        elif cmd == "/say":
            if not arg:
                self.console.print("[red]usage:[/red] /say <text>")
                return
            await self._speak(arg)
        else:
            self.console.print(f"[red]unknown command:[/red] {cmd} (try /help)")

    async def _handle_turn(self, text: str) -> None:
        """One user turn: pretend LLM call, then synthesize & play the reply."""
        self.state.last_user_text = text
        with self.console.status(f"[bold cyan]thinking…[/bold cyan]", spinner="dots"):
            reply = await self._fake_llm(text)
        self.state.last_llm_text = reply
        self.console.print(self._transcript_panel())
        await self._speak(reply)

    async def _fake_llm(self, text: str) -> str:
        """Placeholder LLM (echo with a Portuguese twist) until real LLM is wired."""
        self.bus.publish(LLMComplete(text=f"(echo) {text}", ts=time.monotonic()))
        await asyncio.sleep(0.05)
        return f"(echo) {text}"

    async def _speak(self, text: str) -> None:
        try:
            self.vs.synthesize(
                text,
                profile_id=self.state.voice_id,
                speed=self.state.speed,
                instruct=self.state.instruct,
            )
            self.console.print(f"[dim]🔊 spoke as {self.state.voice_id} @ {self.state.speed:.2f}x[/dim]")
        except Exception as e:  # noqa: BLE001
            self.console.print(f"[red]TTS failed:[/red] {e}")


async def run_cli(config: VoiceAgentConfig) -> int:
    cli = RichCLI(config)
    return await cli.run()
