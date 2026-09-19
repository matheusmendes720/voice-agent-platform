"""MiniMax (M2.5highspeed) streaming chat client — Anthropic-compatible API.

Drop-in replacement for `_call_llm_streaming` in core.py — same signature:
    async def stream(prompt: str, publish) -> None
publishes LLMToken events token-by-token, then LLMComplete(text=full, ts=...).
"""
from __future__ import annotations
import json
import time
from typing import Any

import httpx

from ..events.events import LLMToken, LLMComplete, Error


DEFAULT_BASE = "https://api.minimax.io/anthropic"
DEFAULT_MODEL = "M2.5highspeed"


class MiniMaxStreamClient:
    """MiniMax streaming chat via Anthropic-compatible endpoint.

    SSE event shapes (per MiniMax docs):
      content_block_delta with delta.type == "text_delta"   → response token
      content_block_delta with delta.type == "thinking_delta" → reasoning (skip)
      message_stop                                       → end of stream

    Env vars (read at call time):
      MINIMAX_API_KEY — required
      MINIMAX_BASE_URL — defaults to DEFAULT_BASE
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE,
        model: str = DEFAULT_MODEL,
        system: str = (
            "Você é o assistente de voz do Matheus. Responda em português, "
            "frases curtas e naturais (1-2 frases por turno, max ~25 palavras). "
            "Não use markdown, listas, ou emojis."
        ),
    ) -> None:
        import os
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("MINIMAX_API_KEY env var is required")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.system = system

    async def stream(self, prompt: str, publish) -> None:
        """Stream tokens. `publish` is the bus event publisher."""
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": True,
            "max_tokens": 1024,
            "system": self.system,
            "messages": [
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                ]},
            ],
        }
        full_text_parts: list[str] = []
        url = f"{self.base_url}/v1/messages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "anthropic-version": "2023-06-01",
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as resp:
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        publish(Error(
                            message=f"LLM HTTP {resp.status_code}: {body[:300]!r}",
                            source="llm", ts=time.monotonic(),
                        ))
                        return
                    async for raw_line in resp.aiter_lines():
                        line = raw_line.strip()
                        if not line:
                            continue
                        # Anthropic SSE: lines start with "event:" or "data:"
                        if line.startswith("event:"):
                            continue  # event type lines are redundant; data has it
                        if not line.startswith("data:"):
                            continue
                        chunk = line[5:].strip()
                        if chunk in ("[DONE]", "[done]"):
                            break
                        try:
                            obj = json.loads(chunk)
                        except Exception:
                            continue
                        evt_type = obj.get("type", "")
                        if evt_type == "message_stop":
                            break
                        if evt_type != "content_block_delta":
                            continue
                        delta = obj.get("delta") or {}
                        dtype = delta.get("type", "")
                        if dtype == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                full_text_parts.append(text)
                                publish(LLMToken(token=text, ts=time.monotonic()))
                        # thinking_delta and input_json_delta are ignored on purpose.
        except Exception as e:  # noqa: BLE001
            publish(Error(message=str(e), source="llm", ts=time.monotonic()))
        full = "".join(full_text_parts).strip()
        if full:
            publish(LLMComplete(text=full, ts=time.monotonic()))


async def streaming_llm_factory(prompt: str, publish):
    """Module-level helper matching _call_llm_streaming's signature."""
    client = MiniMaxStreamClient()
    await client.stream(prompt, publish)
