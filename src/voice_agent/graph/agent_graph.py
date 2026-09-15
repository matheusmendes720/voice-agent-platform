"""LangGraph StateGraph for voice agent orchestration."""
from __future__ import annotations
from typing import Literal
from langgraph.graph import StateGraph, END
from ..agent.state import AgentState


def build_agent_graph() -> StateGraph:
    """Build the voice agent StateGraph.

    Nodes:
    - transcribe: Convert audio to text
    - think: Process with LLM
    - act: Execute tools if needed
    - speak: Convert response to audio
    """
    graph = StateGraph(AgentState)

    graph.add_node("transcribe", transcribe_node)
    graph.add_node("think", think_node)
    graph.add_node("act", act_node)
    graph.add_node("speak", speak_node)

    graph.add_edge("transcribe", "think")
    graph.add_conditional_edges(
        "think",
        route_think,
        {"act": "act", "speak": "speak"}
    )
    graph.add_edge("act", "think")
    graph.add_edge("speak", END)

    graph.set_entry_point("transcribe")
    return graph.compile()


async def transcribe_node(state: AgentState) -> AgentState:
    """Transcribe audio to text."""
    return state


async def think_node(state: AgentState) -> AgentState:
    """Process with LLM."""
    return state


async def act_node(state: AgentState) -> AgentState:
    """Execute tools."""
    return state


async def speak_node(state: AgentState) -> AgentState:
    """Convert response to audio."""
    return state


def route_think(state: AgentState) -> Literal["act", "speak"]:
    """Route after think node."""
    if state.tools_results:
        return "act"
    return "speak"
