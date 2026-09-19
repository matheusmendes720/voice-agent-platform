"""Live smoke for MiniMax (M2.5highspeed).

Usage:
    python scripts/test_llm.py
    python scripts/test_llm.py "qual é a capital do Brasil?"
"""
from __future__ import annotations
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from voice_agent.agent.minimax_client import MiniMaxStreamClient
from voice_agent.events.events import LLMToken, LLMComplete, Error


async def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "oi, tudo bem? responde em uma frase."
    print(f"prompt: {prompt!r}")
    print()

    captured: list = []
    t0 = time.monotonic()

    def pub(ev) -> None:
        captured.append(ev)
        if isinstance(ev, LLMToken):
            print(ev.token, end="", flush=True)

    try:
        client = MiniMaxStreamClient()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 2

    await client.stream(prompt, pub)
    elapsed = (time.monotonic() - t0) * 1000

    print()
    print()
    completed = [e for e in captured if isinstance(e, LLMComplete)]
    errors = [e for e in captured if isinstance(e, Error)]
    tokens = [e.token for e in captured if isinstance(e, LLMToken)]

    print(f"elapsed    : {elapsed:.0f} ms")
    print(f"tokens     : {len(tokens)}")
    print(f"completed  : {len(completed)}")
    if errors:
        print(f"ERROR      : {errors[0].message[:200]}")
        return 3
    if not completed:
        print("(no LLMComplete event — empty reply)")
        return 4
    print(f"reply      : {completed[0].text[:200]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
