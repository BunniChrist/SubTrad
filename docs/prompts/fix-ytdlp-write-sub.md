# Agent Prompt: Fix subtitle download using yt-dlp --write-sub

## Branch name
`fix/ytdlp-write-sub`

## Before you start
1. Read `agents.md` at the repo root — follow all rules
2. Announce which superpowers skill you are using
3. You have **full autonomy on reversible decisions** (library choice, implementation approach, etc.)

## Context

SubTrad fetches YouTube subtitles through a 4-step fallback chain. **All HTTP-based methods fail** because YouTube's timedtext API returns 200 with 0 bytes from our server IP, even through a Cloudflare WARP SOCKS5 proxy.

However, `yt-dlp extract_info()` successfully **lists** subtitle tracks and languages. The issue is that we then try to download subtitle content via `httpx.get(subtitle_url)` — which fails because the timedtext URLs require YouTube's internal auth that only yt-dlp handles.

### Current architecture (broken)

```
fetch_captions() in youtube_api.py:
  1. List caption tracks via YouTube Data API v3 → OK (finds tracks)
  2. Download via timedtext public endpoint → FAILS (200 + 0 bytes)
  3. Download via timedtext + kind=asr → FAILS (200 + 0 bytes)
  4. Fall back to fetch_existing_subtitles() in subtitle_fetcher.py:
     a. yt-dlp extract_info() → OK (finds subtitle URLs)
     b. httpx.get(srv3_url) → FAILS (200 + 0 bytes)
```

### Why httpx fails

YouTube timedtext URLs contain signed tokens (`ei=`, `expire=`) but the server still returns empty content. yt-dlp handles this internally with its own download logic, cookie management, and retry mechanisms.

## Task

Rewrite `fetch_existing_subtitles()` in `backend/services/subtitle_fetcher.py` to use **yt-dlp's native subtitle writing** instead of downloading via httpx.

### Implementation plan

1. **Use yt-dlp to write subtitle files to disk**:
   - Use options `writesubtitles=True`, `writeautomaticsub=True`, `subtitlesformat='srv3'`, `subtitleslangs=['all']` (or specific langs)
   - Set `outtmpl` to a temp directory with a predictable filename
   - Use `skip_download=True` (don't download video)
   - Pass `proxy` and `cookiefile` as today

2. **Read the written subtitle file**:
   - After `ydl.download([url])` (not `extract_info`), look for `.srv3` files in the temp dir
   - Parse with `parse_timedtext_xml()` (already exists in `youtube_api.py`)
   - Clean up temp files

3. **Update the fallback chain in `youtube_api.py`**:
   - Steps 1 (API list) stays the same
   - Steps 2-3 (timedtext direct) can stay as-is (fast path, works from some IPs)
   - Step 4: call the rewritten `fetch_existing_subtitles()` which now uses yt-dlp download

4. **Key constraints**:
   - Proxy env var: `SUBTRAD_WARP_PROXY_URL` (socks5h://10.0.1.1:40001) — must be passed to yt-dlp
   - Cookie file: `/root/yt_cookies.txt` — must be passed to yt-dlp
   - Temp files must be cleaned up after use (use `tempfile.mkdtemp` + `finally` block)
   - The function signature `fetch_existing_subtitles(url, proxy, cookie_file)` should not change
   - Keep `parse_srt()` for backward compatibility (other code may use it)

### Example yt-dlp options for subtitle download

```python
import tempfile, os, glob
from yt_dlp import YoutubeDL

tmpdir = tempfile.mkdtemp(prefix="subtrad_")
options = {
    "skip_download": True,
    "writesubtitles": True,
    "writeautomaticsub": True,
    "subtitlesformat": "srv3",
    "subtitleslangs": ["en", "fr", "es", "ja"],  # or target lang + "en"
    "outtmpl": os.path.join(tmpdir, "%(id)s"),
    "quiet": True,
    "no_warnings": True,
    "ignore_no_formats_error": True,
}
if proxy:
    options["proxy"] = proxy
if cookie_file:
    options["cookiefile"] = cookie_file

with YoutubeDL(options) as ydl:
    ydl.download([url])

# Find written subtitle files
sub_files = glob.glob(os.path.join(tmpdir, "*.srv3"))
```

## Tests

- Update `tests/test_subtitle_fetcher.py`:
  - Mock `YoutubeDL.download()` instead of `extract_info()` + `httpx.get()`
  - Verify temp file cleanup
  - Verify proxy and cookie_file are passed
- Run full test suite: `cd backend && python -m pytest tests/ -v`
- All 113+ existing tests must still pass

## Verification

After implementation, test from inside the Docker container:
```bash
docker exec <container> python3 -c "
import sys; sys.path.insert(0, '/app/backend')
from services.subtitle_fetcher import fetch_existing_subtitles
result = fetch_existing_subtitles(
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    proxy='socks5h://10.0.1.1:40001',
    cookie_file='/root/yt_cookies.txt',
)
print('Result:', len(result) if result else None, 'segments')
if result: print('First:', result[0])
"
```

Expected: segments with actual subtitle text, not None.
