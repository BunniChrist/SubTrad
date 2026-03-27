# Agent Prompt: yt-dlp Anti-Bot Bypass for YouTube

## Branch

`fix/ytdlp-anti-bot`

## Context

Read `agents.md` before starting — follow the superpowers framework (TDD, worktrees, verification).

YouTube blocks yt-dlp requests from servers with "Sign in to confirm you're not a bot". This affects both audio extraction (`extract_audio`) and subtitle fetching (`fetch_existing_subtitles`).

## Objective

Add `extractor_args` to all yt-dlp `YoutubeDL` option dicts so YouTube treats the request as a regular web client instead of blocking it. This is a known yt-dlp workaround.

## What to change

### 1. `backend/services/audio_extractor.py` — `extract_audio()`

Add to the `options` dict (after line 27):
```python
"extractor_args": {"youtube": {"player_client": ["web"]}},
```

### 2. `backend/services/subtitle_fetcher.py` — `fetch_existing_subtitles()`

Add to the `options` dict (after line 90):
```python
"extractor_args": {"youtube": {"player_client": ["web"]}},
```

That's it. Two lines added, two files changed.

## Tests

### Update existing tests

In `backend/tests/test_subtitle_fetcher.py`:
- In `test_fetch_existing_subtitles_downloads_and_cleans_up_srv3_files`, add an assertion that `captured_options["extractor_args"]` equals `{"youtube": {"player_client": ["web"]}}`.

In `backend/tests/test_audio_extractor.py`:
- Find or create a test that mocks `YoutubeDL` and captures options. Assert that `captured_options["extractor_args"]` equals `{"youtube": {"player_client": ["web"]}}`.
- If no mock-based test exists, create `test_extract_audio_passes_extractor_args()` that:
  1. Mocks `YoutubeDL` to capture options and create a fake audio file
  2. Calls `extract_audio("https://youtube.com/watch?v=test123", "test123")`
  3. Asserts `extractor_args` is in captured options
  4. Cleans up the fake file

### Do NOT

- Do NOT modify any test that makes real network calls
- Do NOT change function signatures
- Do NOT add new dependencies
- Do NOT touch `youtube_api.py` or `translate.py`

## Verification

Before declaring done:
1. New/updated tests pass
2. All existing tests still pass: `python3 -m pytest backend/tests/ -v`
3. No TODO/FIXME
4. Clean git status

## Autonomy

Full autonomy on reversible decisions. Do NOT ask questions.
