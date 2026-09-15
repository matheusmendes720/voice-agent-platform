"""Tests for config."""
import pytest
from voice_agent.config import VoiceAgentConfig, VoiceStudioConfig, AudioConfig


def test_voicestudio_defaults():
    cfg = VoiceStudioConfig()
    assert cfg.url == "http://127.0.0.1:3900"
    assert cfg.default_voice == "alloy"
    assert cfg.sample_rate == 24000


def test_audio_defaults():
    cfg = AudioConfig()
    assert cfg.sample_rate == 16000
    assert cfg.channels == 1


def test_load_missing_toml():
    cfg = VoiceAgentConfig.from_toml("nonexistent.toml")
    assert cfg.voicestudio.url == "http://127.0.0.1:3900"
