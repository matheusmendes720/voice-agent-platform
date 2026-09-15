"""Agent state for LangGraph."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..events.bus import EventBus


@dataclass
class AgentState:
    """Shared state for the agent graph."""
    messages: list[Any] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    tools_results: dict[str, Any] = field(default_factory=dict)
    interrupted: bool = False
    voice_config: dict[str, Any] = field(default_factory=dict)
    bus: "EventBus | None" = None
