# Agent Prompt: Stabilize Instagram & TikTok Support

## Branch: `feature/instagram-tiktok-stabilize`

## Context

Read `agents.md` before starting. Follow all instructions there (superpowers, TDD, git workflow).

SubTrad supports Instagram (Reels/Posts) and TikTok via the `_handle_ytdlp()` path in `backend/routers/translate.py`. Both platforms share the same pipeline. It works but is **untested and fragile**. Your job is to make it robust for both platforms.

## Current Flow (shared by Instagram & TikTok)

1. URL validation + video ID extraction (already works, tested)
2. `fetch_video_duration_seconds()` via yt-dlp — gets video duration
3. `fetch_existing_subtitles()` via yt-dlp — tries to get captions (almost always None for Instagram/TikTok)
4. `extract_audio()` + `transcribe_audio_with_metadata()` — Whisper fallback
5. `translate_subtitles_with_metadata()` — OpenAI translation
6. Cache + response

## Deliverables

### 1. Test suite for Instagram & TikTok

Create `backend/tests/test_instagram_tiktok.py` with tests covering **both platforms** (parametrize where possible):

- **Happy path**: Reel/TikTok with audio → Whisper transcription → translation → response
- **No audio**: Video where audio extraction fails → graceful error (not a raw 502)
- **Duration limit**: Video exceeding max duration → proper 403 response
- **Existing captions**: Rare case where video has captions → translation works
- **yt-dlp failure**: yt-dlp can't access video (block/rate limit) → meaningful error message
- **Empty transcription**: Whisper returns empty segments → handled gracefully

Mock external calls (yt-dlp, OpenAI) — don't hit real APIs.

### 2. Graceful error handling

Currently if audio extraction fails, the user gets a raw 502. Improve `_handle_ytdlp()` to return **user-friendly error responses**:

- If yt-dlp can't access the video: `{"detail": "Could not access this video. It may be private or unavailable.", "error_code": "platform_access_failed"}`
- If audio extraction fails: `{"detail": "Could not extract audio from this video.", "error_code": "audio_extraction_failed"}`
- If Whisper returns empty: `{"detail": "No speech detected in this video.", "error_code": "no_speech_detected"}`

Return these as proper JSON responses with status 422, not 502.

### 3. Retry logic for yt-dlp extraction

In `_handle_ytdlp()`, add retry with WARP IP rotation when yt-dlp fails on Instagram or TikTok:
- On first failure, check if it's a block (`is_youtube_block` patterns or HTTP 429)
- If blocked, rotate WARP IP and retry once
- This pattern already exists in `youtube_api.py` for YouTube — adapt it

### 4. Test for the recent translation fix

Add a test that verifies:
- When existing captions are fetched in the target language, translation still happens (not skipped)
- This validates the fix from commit `90fa3d1`

## Constraints

- Do NOT modify the YouTube pipeline — only touch `_handle_ytdlp()` and related code
- Tests must be parametrized to cover both Instagram and TikTok URLs
- Do NOT add new dependencies
- All existing 135 tests must still pass
- Use the same patterns/style as existing test files

## Verification

Before declaring done:
1. `python3 -m pytest backend/tests/ -v` — all tests pass (old + new)
2. List all new tests and their purpose
3. Clean git status
