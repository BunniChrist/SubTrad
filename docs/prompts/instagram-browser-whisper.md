# Agent Prompt: Browser-Side Whisper for Instagram & TikTok

## Branch: `feature/browser-whisper`

## Context

Read `agents.md` before starting. Follow all instructions there (superpowers, TDD, git workflow).

**Prerequisite:** Branch `feature/instagram-tiktok-stabilize` must be merged first.

SubTrad currently sends ALL Instagram/TikTok audio to OpenAI's Whisper API for transcription. This costs ~$0.006/minute of audio. For a free app with no revenue on these platforms, this is unsustainable.

## Goal

Add a **browser-side Whisper transcription** option using Transformers.js so that Instagram/TikTok videos are transcribed locally in the user's browser, at zero API cost.

## Architecture

### Backend changes

Add a new response mode. When the backend detects that:
- Platform is Instagram or TikTok
- No existing captions are available

Instead of running Whisper server-side, return a response with:
```json
{
  "platform": "instagram",
  "video_id": "...",
  "subtitles": [],
  "duration_seconds": 45,
  "needs_transcription": true,
  "source": "client_whisper_required",
  "target_lang": "fr",
  "audio_url": "<direct audio URL from yt-dlp>"
}
```

The frontend then handles transcription locally.

### New endpoint: `GET /api/audio/{platform}/{video_id}`

Since browsers can't access Instagram/TikTok audio directly (CORS), create a proxy endpoint:
- Uses yt-dlp to extract the direct audio URL
- Streams/proxies the audio to the browser
- Add rate limiting (same as existing leads endpoint pattern)
- Cache the audio URL (not the file) for 1 hour
- Max duration: same as existing limit

### Frontend changes

Create `frontend/js/whisper-worker.js`:
- Web Worker that loads `@huggingface/transformers` (Whisper tiny or base model)
- Receives audio blob from main thread
- Returns transcribed segments `[{start, end, text}]`
- Shows progress to user (model loading %, transcription %)

Modify `frontend/js/player.js`:
- When response has `source: "client_whisper_required"`:
  1. Show message: "Transcription in progress in your browser..."
  2. Fetch audio from `/api/audio/{platform}/{video_id}`
  3. Send to whisper worker
  4. When segments come back, send them to `POST /api/translate-segments` for translation
  5. Display translated subtitles normally

### New endpoint: `POST /api/translate-segments`

Lightweight endpoint that only does translation (no fetching, no transcription):
```json
{
  "segments": [{"start": 0.0, "end": 2.5, "text": "Hello world"}],
  "target_lang": "fr"
}
```

Returns translated segments. This separates concerns: browser does transcription, server does translation.

## Deliverables

1. **Backend**: Audio proxy endpoint + translate-segments endpoint + modified _handle_ytdlp response
2. **Frontend**: Whisper Web Worker + UI integration with progress indicators
3. **Tests**: Unit tests for both new endpoints, worker message protocol tests
4. **Fallback**: If browser doesn't support Web Workers or WASM, fall back to server-side Whisper (current behavior)

## Technical Decisions (your autonomy)

- Whisper model size (tiny vs base) — balance quality vs download size
- Audio format for browser (wav vs mp3) — balance compatibility vs size
- Transformers.js CDN vs bundled — your call
- Progress UX details — your call

## Constraints

- Do NOT break the YouTube pipeline (YouTube always uses server-side processing)
- Do NOT remove server-side Whisper — it stays as fallback
- Audio proxy must have rate limiting
- Audio proxy must NOT cache audio files on disk (stream only)
- All existing 135 tests must still pass
- Keep frontend vanilla JS (no build tools, no npm for frontend)

## Verification

Before declaring done:
1. `python3 -m pytest backend/tests/ -v` — all tests pass
2. Manual test: describe testing an Instagram Reel in the browser
3. Measure: model download size and transcription time for a 30s video
4. Clean git status
