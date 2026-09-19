"""Tests that VoiceAgent core publishes LLMComplete / Error events."""
import asyncio
import pytest
from voice_agent.events.events import LLMComplete, Error, LLMToken
from voice_agent.events.bus import EventBus
from voice_agent.config import VoiceAgentConfig
from voice_agent.agent.core import VoiceAgent, _call_llm, _call_llm_streaming


@pytest.mark.asyncio
async def test_agent_emits_llm_complete_event(monkeypatch):
    bus = EventBus()
    sub = bus.subscribe()
    cfg = VoiceAgentConfig()

    async def fake_stream(prompt, publish, *, llm_config=None):
        publish(LLMToken(token="olá ", ts=0.0))
        publish(LLMComplete(text="olá do agente", ts=0.0))

    monkeypatch.setattr("voice_agent.agent.core._call_llm_streaming", fake_stream)
    agent = VoiceAgent(cfg, bus=bus)
    await agent._turn("olá usuário")

    saw = []
    for _ in range(5):
        try:
            ev = await asyncio.wait_for(sub.next(), timeout=0.5)
            saw.append(ev)
        except asyncio.TimeoutError:
            break
    await bus.close()
    assert any(isinstance(e, LLMComplete) and e.text == "olá do agente" for e in saw)


@pytest.mark.asyncio
async def test_agent_emits_error_event(monkeypatch):
    bus = EventBus()
    sub = bus.subscribe()
    cfg = VoiceAgentConfig()

    async def bad_stream(prompt, publish, *, llm_config=None):
        raise RuntimeError("LLM exploded")

    monkeypatch.setattr("voice_agent.agent.core._call_llm_streaming", bad_stream)
    agent = VoiceAgent(cfg, bus=bus)
    reply = await agent._turn("anything")

    evs = []
    for _ in range(3):
        try:
            ev = await asyncio.wait_for(sub.next(), timeout=0.5)
            evs.append(ev)
        except asyncio.TimeoutError:
            break
    await bus.close()
    assert reply == ""
    assert any(isinstance(e, Error) and e.source == "llm" for e in evs)


@pytest.mark.asyncio
async def test_default_call_llm():
    # Sanity: the streaming pipeline produces some non-empty reply.
    # If MINIMAX_API_KEY is set, this hits real MiniMax; if not, the echo
    # placeholder is used. Either way the result is non-empty.
    out = await _call_llm("hi")
    assert isinstance(out, str) and len(out) > 0
