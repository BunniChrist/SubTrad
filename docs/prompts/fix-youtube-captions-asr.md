# Fix: YouTube auto-generated captions not detected

## Branch: `fix/youtube-captions-asr`

## Context

SubTrad currently fails to fetch subtitles for YouTube Shorts (and likely many regular videos) that only have **auto-generated captions** (ASR). The user sees "Cette vidéo n'a pas de sous-titres disponibles" even when subtitles exist on YouTube.

**Tested URL:** `https://www.youtube.com/shorts/xowmZ9xLYXE` — has auto-generated subtitles on YouTube, but SubTrad says none available.

## Root cause analysis

The flow in `backend/routers/translate.py` → `_handle_youtube()` calls `fetch_captions()` from `backend/services/youtube_api.py`. Three problems:

### Bug 1: `captions.list` API ignores auto-generated captions
File: `backend/services/youtube_api.py`, line 99-113

The YouTube Data API v3 `captions.list` endpoint only returns **manually uploaded** caption tracks. Auto-generated (ASR) captions are NOT listed. When the video only has ASR captions → `tracks` is empty → returns `None` → user sees "no subtitles".

### Bug 2: Timedtext endpoint missing `kind=asr` parameter
File: `backend/services/youtube_api.py`, line 120-127

The timedtext request uses `?v=ID&lang=xx&fmt=srv3` but auto-generated captions require the additional parameter `kind=asr`. Without it, the endpoint returns empty for ASR-only videos.

### Bug 3: Cookie file not passed to yt-dlp fallback
File: `backend/services/youtube_api.py`, line 130-131
File: `backend/services/subtitle_fetcher.py`, line 31-46

The yt-dlp fallback in `fetch_captions()` calls `fetch_existing_subtitles(youtube_url)` without passing cookies or proxy. Meanwhile, `translate.py` already has cookie handling (line 48-49 with `YOUTUBE_COOKIE_FILE`) but only for `fetch_video_duration_seconds`. YouTube blocks yt-dlp without cookies ("Sign in to confirm you're not a bot").

## Required fixes

### 1. Add ASR fallback in `fetch_captions()` (`youtube_api.py`)

When `captions.list` returns no tracks:
- Before returning `None`, try the timedtext endpoint with `kind=asr` parameter
- Try common languages: the video's detected language first, then `en`, then the target language
- URL format: `https://www.youtube.com/api/timedtext?v={video_id}&lang={lang}&fmt=srv3&kind=asr`

### 2. Fix timedtext request to also try ASR format

In the existing timedtext call (step 3), if the normal request returns empty, retry with `kind=asr` added to params.

### 3. Pass cookies to yt-dlp fallback

- `fetch_captions()` should accept an optional `cookie_file` parameter
- Pass it through to `fetch_existing_subtitles()`
- `fetch_existing_subtitles()` should accept and use `cookiefile` in its yt-dlp options
- In `translate.py`, pass `YOUTUBE_COOKIE_FILE` when calling `fetch_captions_via_api()`

### 4. Pass proxy to yt-dlp fallback

- `fetch_captions()` should accept an optional `proxy` parameter
- Pass it through to `fetch_existing_subtitles()`
- In `translate.py`, pass `settings.proxy_url` when calling `fetch_captions_via_api()`

## Files to modify

- `backend/services/youtube_api.py` — main fix (ASR timedtext + cookie/proxy params)
- `backend/services/subtitle_fetcher.py` — add cookie support
- `backend/routers/translate.py` — pass cookie_file and proxy to fetch_captions
- `backend/tests/test_youtube_api.py` — new/updated tests for ASR flow
- `backend/tests/test_subtitle_fetcher.py` — test cookie passthrough

## Mandatory setup

1. Read `agents.md` — follow all instructions
2. Read `superpowers/using-superpowers/SKILL.md` and announce your superpowers
3. Work on branch `fix/youtube-captions-asr`
4. Use TDD: write failing test → make it pass → commit
5. Full autonomy on reversible decisions (implementation details, test structure, etc.)

## Verification

- All existing tests still pass: `cd backend && python -m pytest tests/ -v`
- New tests cover: ASR timedtext fetch, cookie passthrough, proxy passthrough, fallback chain
- Test with mock: when `captions.list` returns empty, the ASR timedtext path is tried
