# Agent Prompt: WARP IP Rotation — Backend Integration

## Branch name
`feature/warp-ip-rotation`

## Before you start
1. Read `agents.md` at the repo root — follow all rules
2. Read `docs/plans/2026-03-27-warp-rotation-plan.md` for full architecture context
3. Announce which superpowers skill you are using
4. You have **full autonomy on reversible decisions** (implementation details, error handling patterns, etc.)

## Context

SubTrad translates YouTube video subtitles. YouTube frequently blocks requests from server IPs with "Sign in to confirm you're not a bot" or HTTP 429 errors.

A WARP IP rotation HTTP service runs on the host at `http://10.0.1.1:40002/rotate`. When called with `POST /rotate`, it disconnects and reconnects Cloudflare WARP to get a fresh IP. It returns:
- `{"status": "rotated", "new_ip": "x.x.x.x"}` on success
- `{"status": "cooldown", "seconds_remaining": N}` if called too soon (30s cooldown)
- `{"status": "error", "detail": "..."}` on failure

**Your job:** integrate this rotation service into the backend so that when YouTube blocks a request, the backend rotates the IP and retries once.

## Task

### 1. New config field

In `backend/config.py`, add to the Settings class:

```python
warp_rotation_url: str = ""
```

Env var: `SUBTRAD_WARP_ROTATION_URL`

### 2. Create `backend/services/warp_rotator.py`

A simple module with one function:

```python
import httpx
import logging

logger = logging.getLogger(__name__)

def rotate_warp_ip(rotation_url: str, timeout: float = 20.0) -> bool:
    """Call the host WARP rotation service.

    Returns True if rotation succeeded (new IP obtained).
    Returns False on any failure (cooldown, error, unreachable).
    Never raises — failures are logged and swallowed.
    """
```

Key requirements:
- Use `httpx.post(rotation_url, timeout=timeout)`
- Parse JSON response, check `status == "rotated"`
- On cooldown: log warning, return False (do NOT wait for cooldown to expire)
- On connection error (service unreachable): log warning, return False
- On any exception: log warning, return False
- **Never raise exceptions** — this is a best-effort optimization, not a critical path

### 3. Integrate retry logic in `backend/services/subtitle_fetcher.py`

In `fetch_existing_subtitles()`, the yt-dlp download can fail with bot detection or 429.

Current code catches `Exception` after `ydl.download()`. Modify the logic:

1. Catch the download exception
2. Check if the error message contains "Sign in to confirm" or "429"
3. If yes AND a rotation URL is configured:
   - Call `rotate_warp_ip(rotation_url)`
   - If rotation succeeded, retry `ydl.download()` once
4. If retry also fails, continue with the existing behavior (try to parse already-written files)

You need the rotation URL. Get it from settings:
```python
try:
    from backend.config import get_settings
except ModuleNotFoundError:
    from config import get_settings
```
Call `get_settings().warp_rotation_url` only when needed (inside the except block, not at module level).

### 4. Integrate retry logic in `backend/services/youtube_api.py`

In `fetch_captions_via_transcript_lib()`, the youtube-transcript-api can raise `RequestBlocked`.

Modify the except block:
1. Catch the exception
2. If rotation URL is configured, call `rotate_warp_ip()`
3. If rotation succeeded, retry `YouTubeTranscriptApi().fetch()` once
4. If retry fails, return None as before

Import `RequestBlocked` from `youtube_transcript_api._errors` (or catch it by checking the exception type string if the import is fragile).

### 5. Integrate retry logic in `backend/services/audio_extractor.py`

In `extract_audio()`, yt-dlp can fail with bot detection when downloading audio.

Wrap the `ydl.extract_info()` call:
1. Catch `DownloadError` (from `yt_dlp.utils`)
2. Check if error contains "Sign in to confirm" or "429"
3. If yes AND rotation URL configured, rotate and retry once
4. If retry fails, raise the original exception (audio extraction failure should still propagate)

### 6. Pattern to follow everywhere

```python
# Attempt 1
try:
    result = do_youtube_thing()
except (SpecificError, Exception) as exc:
    if not _is_youtube_block(exc):
        raise  # or return None — depends on existing behavior

    # Attempt rotation
    rotation_url = get_settings().warp_rotation_url
    if not rotation_url or not rotate_warp_ip(rotation_url):
        raise  # or return None

    # Attempt 2 (single retry)
    result = do_youtube_thing()
```

Create a small helper `_is_youtube_block(exc) -> bool` in `warp_rotator.py`:
```python
_BLOCK_PATTERNS = ["Sign in to confirm", "HTTP Error 429", "RequestBlocked"]

def is_youtube_block(exc: Exception) -> bool:
    msg = str(exc)
    return any(pattern in msg for pattern in _BLOCK_PATTERNS)
```

## What NOT to do

- Do NOT create the host-side rotation service (warp-rotate.py) — that's separate infra work
- Do NOT modify the fallback chain order or any other logic
- Do NOT add retry loops — maximum 1 retry per request, no loops
- Do NOT wait/sleep for cooldown to expire — if cooldown, just skip and continue
- Do NOT make rotation URL required — if not configured, all code behaves exactly as before
- Do NOT import settings at module level — only call `get_settings()` inside functions when needed

## Tests

### `backend/tests/test_warp_rotator.py` (new)

1. **Successful rotation**: mock httpx.post returning `{"status": "rotated", "new_ip": "1.2.3.4"}` → returns True
2. **Cooldown response**: mock returning `{"status": "cooldown", "seconds_remaining": 20}` → returns False
3. **Error response**: mock returning `{"status": "error", "detail": "warp-cli failed"}` → returns False
4. **Service unreachable**: mock raising `httpx.ConnectError` → returns False, no exception raised
5. **is_youtube_block**: test with "Sign in to confirm you're not a bot" → True, "Some other error" → False

### `backend/tests/test_subtitle_fetcher.py` (update)

6. **Retry after rotation**: yt-dlp download raises "Sign in" error → rotation called → retry succeeds → segments returned
7. **No retry when no rotation URL**: same error but `warp_rotation_url=""` → no rotation call, existing behavior

### `backend/tests/test_youtube_api.py` (update)

8. **Retry transcript-api after rotation**: RequestBlocked raised → rotation → retry succeeds → segments returned
9. **No retry when rotation fails**: RequestBlocked → rotation returns False → returns None

### `backend/tests/test_audio_extractor.py` (update or create)

10. **Retry audio extraction after rotation**: DownloadError "Sign in" → rotation → retry succeeds → audio path returned
11. **Propagates error after failed retry**: rotation succeeds but retry also fails → exception raised

Mock `rotate_warp_ip` and `get_settings` in all integration tests. Do NOT call the real rotation service.

## Verification

Before declaring done:
1. New tests pass: `python3 -m pytest backend/tests/test_warp_rotator.py -v`
2. All existing tests still pass: `python3 -m pytest backend/tests/ -v`
3. No TODO/FIXME left behind
4. Clean git status
5. Verify backward compatibility: with `SUBTRAD_WARP_ROTATION_URL=""`, all code must behave exactly as before (no rotation, no retries)

## Autonomy

Full autonomy on reversible decisions. Do NOT ask questions.
