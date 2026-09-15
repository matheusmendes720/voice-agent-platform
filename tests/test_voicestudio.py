"""Tests for VoiceStudio client (mocked)."""
import pytest
from voice_agent.voice.voicestudio import VoiceStudioClient, SynthesisResult


class TestVoiceStudioClient:
    def test_initialization(self):
        client = VoiceStudioClient("http://127.0.0.1:3900")
        assert client.base_url == "http://127.0.0.1:3900"

    def test_synthesis_result(self):
        result = SynthesisResult(audio_bytes=b"test", duration_ms=100)
        assert result.audio_bytes == b"test"
        assert result.duration_ms == 100
