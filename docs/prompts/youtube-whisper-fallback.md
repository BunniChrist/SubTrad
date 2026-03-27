# Agent Prompt: YouTube Whisper Fallback

## Branch

`feature/youtube-whisper-fallback`

## Context

Read `agents.md` before starting — follow the superpowers framework (TDD, worktrees, verification).

SubTrad is a video subtitle translation app. When a user submits a YouTube URL:
1. `fetch_captions` in `backend/services/youtube_api.py` tries YouTube Data API v3, timedtext, and yt-dlp fallback
2. If all return `None` → the app returns `{"redirect": "/premium.html", "reason": "no_captions"}`

**Problem:** Many YouTube videos (especially Shorts) have no captions at all. The app gives up instead of transcribing the audio.

**For TikTok/Instagram**, a Whisper fallback already exists in `_handle_ytdlp()` (lines 278-324 of `backend/routers/translate.py`). It extracts the audio, transcribes with Whisper, then translates.

**For YouTube**, this fallback is missing. The `_handle_youtube()` function (lines 128-213) returns `no_captions` at line 178-185 instead of falling back to Whisper.

## Objective

When `fetch_captions_via_api()` returns `None` in `_handle_youtube()`, instead of returning `no_captions`, fall back to the same Whisper transcription pipeline already used for TikTok/Instagram:
1. Extract audio with `extract_audio(url, video_id, proxy=...)`
2. Transcribe with `transcribe_audio_with_metadata(audio_path, openai_api_key)`
3. Translate with `translate_subtitles_with_metadata()`
4. Build response with `source="whisper_transcription"` and `needs_transcription=True`
5. Clean up audio file in `finally` block

## What to change

**File: `backend/routers/translate.py`**

Replace lines 178-185 (the `if subtitles is None: return no_captions` block) with the Whisper fallback pipeline. Use the same pattern as `_handle_ytdlp()` lines 278-324.

The imports for `extract_audio`, `cleanup_audio`, `transcribe_audio_with_metadata` are already present.

## What NOT to do

- Do NOT refactor or extract a shared helper — keep it simple, duplicate the pattern
- Do NOT modify `_handle_ytdlp()` or any other function
- Do NOT touch `youtube_api.py` or `subtitle_fetcher.py`
- Do NOT add any new dependencies

## Tests

Write tests in `backend/tests/test_translate_youtube_whisper.py` covering:

1. **Happy path**: `fetch_captions_via_api` returns `None` → `extract_audio` is called → `transcribe_audio_with_metadata` returns segments → `translate_subtitles_with_metadata` returns translated segments → response has `source="whisper_transcription"` and `needs_transcription=True`
2. **Whisper failure**: `extract_audio` or `transcribe_audio_with_metadata` raises an exception → response is 502 with error detail
3. **Audio cleanup**: audio file is cleaned up even when transcription fails (verify `cleanup_audio` is called in both success and failure cases)

Mock all external calls (`get_video_info`, `fetch_captions_via_api`, `extract_audio`, `transcribe_audio_with_metadata`, `translate_subtitles_with_metadata`). Use `monkeypatch` or `unittest.mock.patch`.

## Verification

Before declaring done:
1. New tests pass: `python3 -m pytest backend/tests/test_translate_youtube_whisper.py -v`
2. All existing tests still pass: `python3 -m pytest backend/tests/ -v`
3. No TODO/FIXME left behind
4. Clean git status

## Autonomy

Full autonomy on reversible decisions. Do NOT ask questions.
