# Agent Prompt: Add youtube-transcript-api as Primary Fast Path

## Branch name
`feature/youtube-transcript-api`

## Before you start
1. Read `agents.md` at the repo root — follow all rules
2. Announce which superpowers skill you are using
3. You have **full autonomy on reversible decisions** (library choice, implementation approach, etc.)

## Context

SubTrad is a video subtitle translation app. When a user submits a YouTube URL, `_handle_youtube()` in `backend/routers/translate.py` calls `fetch_captions_via_api()` in `backend/services/youtube_api.py` to get subtitles.

**Problem:** All HTTP-based subtitle fetching methods fail from the server (YouTube returns 200 + 0 bytes). The current fallback chain is unreliable.

**Solution:** Add `youtube-transcript-api` as the **first** method tried — before the existing YouTube Data API v3 call. This Python library fetches YouTube captions using YouTube's internal API, without needing:
- YouTube Data API key (saves quota)
- yt-dlp (faster, lighter)
- Proxy or cookies (handles auth internally)

## Task

### 1. Install dependency

```bash
pip install youtube-transcript-api
```

Add `youtube-transcript-api` to `backend/requirements.txt`.

### 2. Create fast path function in `backend/services/youtube_api.py`

Add a new function that tries `youtube-transcript-api` first:

```python
from youtube_transcript_api import YouTubeTranscriptApi

def fetch_captions_via_transcript_lib(video_id: str, preferred_langs: list[str] | None = None) -> list[dict] | None:
    """Fast path: fetch captions via youtube-transcript-api library.

    Tries to get captions without API key, proxy, or cookies.
    Returns list of {"text": str, "start": float, "duration": float} or None.
    """
    langs = preferred_langs or ["en", "fr", "es", "ja", "de", "pt", "it", "ar", "zh", "ko", "ru"]
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=langs)
        segments = [
            {"text": entry.text, "start": entry.start, "duration": entry.duration}
            for entry in transcript.snippets
        ]
        if segments:
            return segments
        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"youtube-transcript-api failed for {video_id}: {e}")
        return None
```

**Important:** Check the actual API of the `youtube-transcript-api` library. The snippet above is a guide — adapt to the real API. The library may use `YouTubeTranscriptApi.get_transcript(video_id)` or similar. Read the library source or docs to confirm.

Key points:
- Return format must match what `translate_subtitles_with_metadata()` expects: list of dicts with `text`, `start`, `duration`
- Catch ALL exceptions (network errors, no transcript available, etc.) — return `None` on failure
- Log warnings on failure for debugging

### 3. Integrate into the fallback chain in `backend/services/youtube_api.py`

Find the main caption-fetching function (`fetch_captions_via_api` or `fetch_captions`) and insert the new function as the **first step**:

```python
# Step 0 (NEW): Try youtube-transcript-api (fast, no API key needed)
segments = fetch_captions_via_transcript_lib(video_id)
if segments:
    return segments

# Step 1 (existing): Try YouTube Data API v3...
# ... rest of existing code unchanged
```

### 4. Update `_handle_youtube()` in `backend/routers/translate.py`

The response should include `source` metadata. When captions come from youtube-transcript-api, set:
- `source="youtube_transcript_api"` (or similar identifier)

Check how the existing code sets `source` for other methods and follow the same pattern. If source is determined by the return value of `fetch_captions_via_api()`, you may need to return a tuple or add a flag.

**Simplest approach:** If `fetch_captions_via_api()` currently returns just a list, and `source` is set elsewhere, just make sure the new path integrates cleanly without breaking the existing source detection.

## What NOT to do

- Do NOT modify `subtitle_fetcher.py` — that's for a separate fix
- Do NOT modify `_handle_ytdlp()` — TikTok/Instagram path is unrelated
- Do NOT add proxy or cookie support to the new function — the whole point is it doesn't need them
- Do NOT remove existing fallback methods — they stay as backup
- Do NOT refactor the existing fallback chain — just prepend the new step

## Tests

Create `backend/tests/test_youtube_transcript_api.py`:

1. **Happy path**: `youtube-transcript-api` returns transcript → function returns formatted segments
2. **Library not available or fails**: exception raised → function returns `None`, no crash
3. **Empty transcript**: library returns empty list → function returns `None`
4. **Integration with fallback chain**: when transcript-api returns `None`, the existing methods are still called (mock both paths)
5. **Segment format**: verify each segment has `text` (str), `start` (float), `duration` (float)

Mock `YouTubeTranscriptApi` — do NOT make real network calls in tests.

## Verification

Before declaring done:
1. New tests pass: `python3 -m pytest backend/tests/test_youtube_transcript_api.py -v`
2. All existing tests still pass: `python3 -m pytest backend/tests/ -v`
3. No TODO/FIXME left behind
4. Clean git status
5. Verify the import works: `python3 -c "from youtube_transcript_api import YouTubeTranscriptApi; print('OK')"`

## Autonomy

Full autonomy on reversible decisions. Do NOT ask questions.
