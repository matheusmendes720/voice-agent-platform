"""Tests for TranscriptWidget."""
from voice_agent.hud.widgets.transcript import TranscriptWidget


def test_transcript_appends_user_line():
    w = TranscriptWidget()
    # Stub the Textual update so we don't need an active app.
    w.update = lambda *_a, **_k: None  # type: ignore[assignment]
    w.append("user", "olá")
    w.append("assistant", "oi! tudo bem?")
    rendered = "\n".join(w._lines)
    assert "user: olá" in rendered
    assert "assistant: oi! tudo bem?" in rendered


def test_transcript_caps_history():
    w = TranscriptWidget(max_lines=3)
    w.update = lambda *_a, **_k: None  # type: ignore[assignment]
    for i in range(10):
        w.append("user", f"msg {i}")
    assert len(w._lines) == 3
