# Agent Prompt — Phase 2: Whisper Transcription

## Setup

- **Branch:** `feature/whisper-transcription`
- **Working directory:** `/root/Workspace/SubTrad`
- **First steps:**
  1. Read `agents.md` and follow it
  2. Read `superpowers/using-superpowers/SKILL.md` and announce your skill
  3. Create and switch to branch `feature/whisper-transcription`
  4. Read `docs/subtrad-framing.md` for full product context

## Goal

Add audio extraction and Whisper transcription as a fallback when no existing subtitles are found. This connects to the Phase 1 backend: when `subtitle_fetcher` returns no subtitles, we extract audio, transcribe with Whisper, and return timestamped segments.

## Context — What Already Exists

Phase 1 is complete on `main`. You have:
- `backend/main.py` — FastAPI app with CORS
- `backend/routers/translate.py` — POST /api/translate endpoint (returns `needs_transcription: true` when no subs found)
- `backend/services/subtitle_fetcher.py` — Fetches existing YouTube captions via yt-dlp
- `backend/services/url_validator.py` — URL validation + platform detection
- `backend/services/video_id.py` — Video ID extraction
- `backend/services/duration_checker.py` — Max 12 min check
- `backend/models.py` — Pydantic models (TranslateRequest, TranslateResponse)
- `backend/config.py` — Settings with `get_settings()`

## Tech Stack

- yt-dlp (already in requirements.txt) — for audio-only extraction
- OpenAI Whisper API (`openai` Python package) — for transcription
- Use the **API** (not local model) to keep server lightweight. The user has 10 EUR on their OpenAI account.

## API Key

The OpenAI API key is stored in `/root/SECRETS.md`. Read it to get the key.
Add `openai_api_key: str = ""` to `backend/config.py` Settings, loaded via env var `SUBTRAD_OPENAI_API_KEY`.

## Directory Structure — New Files

```
backend/
  services/
    audio_extractor.py    — NEW: extract audio from video URL to temp file
    transcriber.py        — NEW: Whisper API transcription
  tests/
    test_audio_extractor.py   — NEW
    test_transcriber.py        — NEW
    fixtures/                  — NEW: short test audio file(s)
```

## Tasks (TDD — test first, implement, commit)

### Task 1: Add OpenAI dependency + config

Add `openai>=1.0.0` to `backend/requirements.txt`.
Add `openai_api_key: str = ""` to the Settings class in `backend/config.py`.
Install dependencies: `pip install -r backend/requirements.txt`

Commit: `feat: add openai dependency and api key config`

### Task 2: Audio extractor service

Create `backend/services/audio_extractor.py` with:
- `extract_audio(url: str, video_id: str) -> str` — uses yt-dlp to download audio-only (mp3 or m4a) to a temp directory. Returns the file path.
- `cleanup_audio(path: str) -> None` — deletes the temp audio file.

Requirements:
- Audio must be saved in `/tmp/subtrad/` or similar temp directory
- File named by video_id to avoid collisions (e.g. `/tmp/subtrad/dQw4w9WgXcQ.mp3`)
- yt-dlp options: audio-only, best audio quality, no video
- Must work for YouTube, Instagram, TikTok URLs
- Cleanup must not raise if file doesn't exist

Tests (`backend/tests/test_audio_extractor.py`):
- Test that `extract_audio` returns a valid file path ending in audio extension
- Test that the file exists after extraction
- Test that `cleanup_audio` removes the file
- Test that `cleanup_audio` on non-existent file doesn't raise
- **For unit tests**: mock yt-dlp to avoid real downloads. Create a small fixture audio file for fast tests.
- **One integration test** (marked with `@pytest.mark.integration`): test with a real short YouTube URL (use `https://www.youtube.com/watch?v=jNQXAC9IVRw` — first YouTube video ever, 19 seconds)

### Task 3: Whisper transcription service

Create `backend/services/transcriber.py` with:
- `transcribe_audio(audio_path: str, api_key: str) -> list[dict]` — sends audio to OpenAI Whisper API, returns segments as `[{"start": float, "end": float, "text": str}]`

Requirements:
- Use `openai.OpenAI(api_key=api_key)` client
- Use `client.audio.transcriptions.create(model="whisper-1", file=..., response_format="verbose_json", timestamp_granularities=["segment"])`
- Extract segments from the response
- Handle empty audio (return empty list)
- Detect language automatically (Whisper does this natively)

Tests (`backend/tests/test_transcriber.py`):
- Test with a mocked OpenAI response: verify segments are correctly parsed
- Test empty audio returns empty list
- Test that timestamps are floats
- **One integration test** (marked `@pytest.mark.integration`): transcribe `backend/tests/fixtures/` test audio file with real Whisper API

### Task 4: Create test fixture

Create a small test audio file at `backend/tests/fixtures/test_audio.mp3`:
- Generate a short (2-3 second) audio file with TTS or a simple tone
- Or download a tiny public domain clip
- This is used by unit tests to avoid real API calls

### Task 5: Wire transcription into translate endpoint

Modify `backend/routers/translate.py`:
- When `subtitle_fetcher` returns no subtitles (currently returns `needs_transcription: true`):
  1. Call `extract_audio(url, video_id)`
  2. Call `transcribe_audio(audio_path, settings.openai_api_key)`
  3. Call `cleanup_audio(audio_path)`
  4. Return the transcribed segments as subtitles (untranslated — translation comes in Phase 3)
- Keep the `needs_transcription` flag in response but now also populate `subtitles` with transcribed segments
- Add proper error handling: if extraction or transcription fails, return a clear error

Modify `backend/models.py` if needed:
- Ensure TranslateResponse can carry `source: str` field ("existing_captions" or "whisper_transcription")

Tests (`backend/tests/test_translate_endpoint.py`):
- Add test: valid URL with no existing subs triggers transcription pipeline (mock the services)
- Add test: transcription failure returns appropriate error

### Task 6: Verification

- [ ] All existing tests still pass: `python -m pytest backend/tests/ -v` (skip integration tests with `-m "not integration"`)
- [ ] Integration test passes: `python -m pytest backend/tests/ -v -m integration` (requires OpenAI API key)
- [ ] Server starts: `cd backend && uvicorn main:app --host 0.0.0.0 --port 8010`
- [ ] POST /api/translate with a YouTube URL that has no subs triggers Whisper transcription
- [ ] Temp audio files are cleaned up after processing
- [ ] All code committed on `feature/whisper-transcription`
- [ ] No TODO/FIXME left
- [ ] Clean `git status`
