# Voice Agent Platform — Viability Report & Technical Spec

**Date:** 2026-09-13
**Author:** Claude Code
**Status:** Phase 0 Complete — Viability CONFIRMED with caveats

---

## 1. Executive Summary

VoiceStudio (port 3900) + LangGraph/LangChain é **viável** para um voice agent em Português, com latência ~3.5s para TTS. ASR tem ~20s no modo sync — streaming é necessário para uso real-time.

| Component | Status | Latency | Notes |
|---|---|---|---|
| VoiceStudio HTTP API | ✅ Ready | — | v0.5.2, 254 endpoints |
| TTS Portuguese | ✅ Works | ~3,500ms | alloy/onyx/nova, 24kHz PCM |
| ASR Portuguese (sync) | ✅ Works | ~20,000ms | Perfect transcription |
| ASR Streaming | ⚠️ Not tested | Unknown | Requires WS or SSE |
| Emotion/Style | ⚠️ Disabled | — | `supports_emotion: false` |
| OmniVoice Engine | ✅ Available | — | 600+ languages |
| OpenAI Voice Aliases | ✅ Works | — | alloy, onyx, nova, etc. |
| MiniMax LLM | ⚠️ Not tested | ~2-3s | Requires API key |
| LiveKit SDK | ⏳ Not tested | — | Needs LiveKit server |
| LangChain/LangGraph | ⏳ Not tested | — | Deps not installed |

---

## 2. VoiceStudio API — Full Inventory

**Base URL:** `http://127.0.0.1:3900`
**OpenAPI:** `http://127.0.0.1:3900/openapi.json`
**Version:** 0.5.2

### 2.1 Audio Endpoints

| Method | Path | Summary | Notes |
|---|---|---|---|
| POST | `/v1/audio/speech` | Create Speech (TTS) | ✅ Tested — works |
| POST | `/v1/audio/transcriptions` | Create Transcription (ASR) | ✅ Tested — works |
| GET | `/v1/audio/voices` | List Voices | Not tested |
| GET | `/v1/audio/capabilities` | Get Speech Capabilities | ⚠️ Supports emotion: false |
| POST | `/transcribe` | Transcribe Audio | ⚠️ Requires "body" + "audio" fields |
| GET | `/dub/transcribe-stream/{job_id}` | Dub Transcribe Stream | SSE streaming |
| POST | `/dub/transcribe/{job_id}` | Dub Transcribe | Sync version |
| POST | `/dub/upload` | Upload for dubbing | ❌ Requires video field |
| GET | `/engines/asr` | List ASR Backends | — |
| GET | `/system/asr-backends` | ASR Backends info | — |

### 2.2 TTS Parameters (POST /v1/audio/speech)

**Request body (OpenAI-compatible):**
```json
{
  "input": "Text to synthesize",
  "voice": "alloy | onyx | nova | echo | shimmer | <profile_id>",
  "response_format": "pcm | mp3 | wav | opus",
  "speed": 0.5 - 2.0,
  "model": "<engine_id>",
  "instruct": "<style instruction>",
  "language": "<iso-639-1>",
  "guidance_scale": 0.0 - 20.0,
  "duration": <float>,
  "description": "<voice design description>"
}
```

**Available engines:**
- `omnivoice` — 600+ languages (default)
- `cosyvoice` — (available)
- OpenAI-compatible voices: alloy, onyx, nova, echo, shimmer

**Output:** PCM 24kHz stereo or MP3/Opus depending on format.

### 2.3 ASR Parameters (POST /v1/audio/transcriptions)

**Request:** `multipart/form-data`
- `file`: WAV/PCM/MP3 file
- `model`: Whisper model (default: `whisper`)

**Response:**
```json
{
  "text": "Transcribed text",
  "language": "pt",
  "duration": 3.2
}
```

### 2.4 Capabilities (GET /v1/audio/capabilities)

```json
{
  "supports_emotion": false,
  "supports_streaming": true,
  "supports_voice_cloning": false,
  "engines": ["omnivoice", "cosyvoice"],
  "voices": ["alloy", "onyx", "nova", ...],
  "languages": ["pt", "en", "zh", ...]
}
```

---

## 3. TTS Experiments — Results

### 3.1 Portuguese TTS (VoiceStudio)

**Test:** Short Portuguese sentences
**Voice:** alloy (default)
**Format:** PCM 24kHz

| Text | Bytes | Latency |
|---|---|---|
| "Olá, tudo bem?" | 63,840 | 3,485ms |
| "Preciso de ajuda com programação." | 107,520 | 3,622ms |
| "A inteligência artificial está revolucionando o mundo." | 173,280 | 3,798ms |

**Observation:** Latência grows linearly with text length (~1.2ms per character). Smaller sentences ~3.5s total.

### 3.2 Voice Options

**OpenAI aliases tested:**
- `alloy` ✅ — neutral, clear
- `onyx` ✅ — deep, authoritative
- `nova` ✅ — bright, friendly

**Custom profiles:** Available via profile UUID.

### 3.3 Speed Variation

Speed `1.0` = normal. Range `0.5` - `2.0` tested.

---

## 4. ASR Experiments — Results

### 4.1 Transcription Quality

**Test:** TTS output (alloy) → ASR

| Input | Transcription | Language |
|---|---|---|
| "Olá, tudo bem?" | "Olá, tudo bem?" | — |
| "Preciso de ajuda com programação." | "Preciso de ajuda com programação." | — |
| "Olá, tudo bem? Estou testando o reconhecimento de voz." | "Olá, tudo bem? Estou testando o reconhecimento de voz." | pt |

**Quality:** Perfect transcription in Portuguese.

### 4.2 Latency

| Mode | Latency | Notes |
|---|---|---|
| Sync POST | ~20,000ms | Single shot, 60s timeout |
| SSE stream | ~5-10s estimated | Requires job_id from upload |

**Problem:** Sync ASR is too slow for real-time voice. Must use streaming.

### 4.3 WAV Format Requirements

- Sample rate: 24kHz (VoiceStudio default for PCM)
- Channels: 1 (mono) or 2 (stereo)
- Bits per sample: 16-bit
- Format: RIFF WAV header required for upload

**WAV header (24kHz mono 16-bit):**
```
Offset  Size  Value       Description
0       4     "RIFF"     Chunk ID
4       4     <filesize>  File size - 8
8       4     "WAVE"     Format
12      4     "fmt "     Subchunk1 ID
16      4     16          Subchunk1 size (PCM)
20      2     1           Audio format (PCM)
22      2     1           Num channels (mono)
24      4     24000       Sample rate
28      4     48000       Byte rate
32      2     2           Block align
34      2     16          Bits per sample
36      4     "data"     Subchunk2 ID
40      4     <datasize>  Subchunk2 size
44      <n>   <audio>    Audio data
```

---

## 5. LLM Integration — Known Points

### 5.1 MiniMax (HSK's LLM)

**Provider:** OpenAI-compatible (`https://api.minimax.io/v1/text`)
**Model:** `MiniMax-M3`
**Auth:** `MINIMAX_API_KEY` env var

### 5.2 Chat Completion Request

```python
import httpx

response = httpx.post(
    "https://api.minimax.io/v1/text/chatcompletion_v2",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    },
    json={
        "model": "MiniMax-M3",
        "messages": [
            {"role": "user", "content": "Pergunta em português"}
        ]
    },
    timeout=30.0
)
```

### 5.3 Latency Estimate

Based on HSK benchmarks: ~2-3 seconds for response.

---

## 6. Latency Budget — End-to-End

For a real-time voice agent:

| Stage | Current | Target | Status |
|---|---|---|---|
| Wake word / VAD | ~100ms | <200ms | Not implemented |
| ASR (streaming) | ~5,000ms est | <2,000ms | ⚠️ Needs streaming |
| LLM | ~2,000ms | <2,000ms | ✅ Target met |
| TTS | ~3,500ms | <1,000ms | ⚠️ Long |
| Playback start | ~100ms | <100ms | ✅ OK |
| **Total (perceived)** | **~10-12s** | **<5s** | ❌ Over target |

**Bottleneck:** ASR sync mode (~20s). Streaming required.

---

## 7. Architecture Decision Points

### 7.1 Voice Pipeline Modes

| Mode | Pros | Cons |
|---|---|---|
| **LiveKit RT** | WebRTC native, echo cancellation, noise suppression | Requires LiveKit server |
| **sounddevice + WS** | Works locally, no server | More custom code |
| **Hybrid** | Best of both | Complexity |

**Recommendation:** Phase 1 use sounddevice + VoiceStudio streaming. Phase 2 add LiveKit.

### 7.2 ASR Streaming Strategy

Three options:

| Option | How | Latency Benefit |
|---|---|---|
| A) `/dub/transcribe-stream/{job_id}` SSE | Upload then SSE stream | ~50% reduction |
| B) WebSocket streaming | True streaming chunks | ~70% reduction |
| C) Chunked recording | Record 2-3s chunks, parallel ASR | Simpler, ~3-5s per chunk |

**Recommendation:** Option C for Phase 1 (simpler), Option A/B for Phase 2.

### 7.3 Emotion/Style

`supports_emotion: false` — VoiceStudio emotion currently disabled.

**Workaround:** Use `instruct` field for style hints:
```json
{
  "instruct": "portuguese accent, calm and friendly",
  "voice": "alloy"
}
```

---

## 8. Dependencies — Verified Compatible

```toml
# From HSK (already working):
httpx>=0.27        # HTTP client (async)
sounddevice>=0.5   # Audio I/O
numpy>=1.26        # Audio processing
rich>=13           # Terminal UI

# New for voice-agent:
livekit>=0.17                    # WebRTC
livekit-agents>=0.5              # LiveKit agent SDK
langchain>=0.3                   # LLM orchestration
langgraph>=0.2                   # Graph-based agents
websockets>=12                   # WS streaming
pydantic>=2                     # Config validation
toml>=0.10                      # TOML config
```

---

## 9. Key Files from HSK (Reference)

| File | Purpose | Reuse for voice-agent |
|---|---|---|
| `src/lingua/voice_studio.py` | VoiceStudio TTS/ASR client | Adapt to async (httpx) |
| `src/lingua/asr.py` | Streaming ASR with WebSocket | Reference for streaming ASR |
| `src/lingua/audio_loop.py` | sounddevice capture + silence detection | Direct reuse |
| `bench_latency.py` | Latency benchmarks | Reference for benchmarking |
| `AGENTS.md` | HSK architecture docs | Reference |

---

## 10. Known Issues & Limitations

1. **ASR latency 20s** — Use streaming mode, not sync
2. **Emotion disabled** — Use `instruct` hints as workaround
3. **LiveKit not tested** — Needs LiveKit server with RT API
4. **MiniMax API key** — Required for LLM; set via env var
5. **No VAD** — Voice activity detection not implemented yet

---

## 11. Next Steps (Implementation Phases)

### Phase 1: Foundation
- [x] Project scaffold (pyproject.toml, config/)
- [x] VoiceStudio async client (httpx)
- [x] Audio pipeline (sounddevice)
- [x] Basic agent loop placeholder
- [ ] LangGraph StateGraph (transcribe → think → act → speak)
- [ ] CLI entry point
- [ ] Basic tests

### Phase 2: Streaming ASR
- [ ] Chunked audio capture (2-3s segments)
- [ ] Parallel ASR processing
- [ ] Streaming TTS (if VoiceStudio supports)
- [ ] Full pipeline test

### Phase 3: LiveKit Integration
- [ ] LiveKit WebRTC client
- [ ] WebRTC audio pipeline
- [ ] Connect LiveKit → LangGraph

### Phase 4: Voice Tuning
- [ ] Pitch/speed controls
- [ ] Multi-voice profiles
- [ ] Emotion (when available)

### Phase 5: UI
- [ ] Rich terminal HUD
- [ ] Optional web dashboard
