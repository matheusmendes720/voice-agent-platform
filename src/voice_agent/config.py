"""Configuration dataclasses for voice-agent."""
from dataclasses import dataclass, field
from pathlib import Path
import tomllib


@dataclass
class VoiceStudioConfig:
    url: str = "http://127.0.0.1:3900"
    default_voice: str = "alloy"
    engine: str = "omnivoice"
    sample_rate: int = 24000


@dataclass
class LLMConfig:
    provider: str = "minimax"
    model: str = "MiniMax-M3"
    api_key: str = ""


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    chunk_ms: int = 100
    channels: int = 1


@dataclass
class AgentConfig:
    name: str = "VoiceAgent"
    language: str = "pt"
    max_history: int = 10


@dataclass
class VoiceAgentConfig:
    voicestudio: VoiceStudioConfig = field(default_factory=VoiceStudioConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)

    @classmethod
    def from_toml(cls, path: str | Path) -> "VoiceAgentConfig":
        path = Path(path)
        if not path.exists():
            return cls()
        text = path.read_text(encoding="utf-8")
        data = tomllib.loads(text)
        vs = data.get("voicestudio", {})
        llm = data.get("llm", {})
        audio = data.get("audio", {})
        agent = data.get("agent", {})
        return cls(
            voicestudio=VoiceStudioConfig(**vs),
            llm=LLMConfig(**llm),
            audio=AudioConfig(**audio),
            agent=AgentConfig(**agent),
        )
