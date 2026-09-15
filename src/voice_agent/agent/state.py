"""Agent state for LangGraph."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    """Shared state for the agent graph."""
    messages: list[Any] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    tools_results: dict[str, Any] = field(default_factory=dict)
    interrupted: bool = False
    voice_config: dict[str, Any] = field(default_factory=dict)
