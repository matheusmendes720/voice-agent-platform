"""LiveKit Realtime API integration.

Currently a placeholder - LiveKit integration is Phase 2.
"""
from __future__ import annotations


class LiveKitVoiceClient:
    """LiveKit WebRTC voice client."""

    def __init__(
        self,
        url: str = "wss://your-livekit-server.com",
        api_key: str = "",
        api_secret: str = "",
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret
        self._room = None

    async def connect(self) -> None:
        """Connect to LiveKit room."""
        raise NotImplementedError("LiveKit integration pending Phase 2")

    async def disconnect(self) -> None:
        """Disconnect from LiveKit room."""
        if self._room:
            await self._room.disconnect()
            self._room = None

    async def send_audio(self, audio_bytes: bytes) -> None:
        """Send audio bytes to the room."""
        if self._room is None:
            raise RuntimeError("Not connected")
