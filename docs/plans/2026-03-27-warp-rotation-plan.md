# Plan: On-demand WARP IP Rotation

**Date:** 2026-03-27
**Goal:** When YouTube blocks a request (429 or bot detection), automatically rotate the WARP IP and retry.

## Architecture

```
Container (SubTrad backend)                    Host (Contabo VPS)
┌──────────────────────────┐                  ┌──────────────────────────┐
│                          │                  │                          │
│  yt-dlp / transcript-api │                  │  warp-rotation.service   │
│         ↓ fails          │                  │  (Python HTTP on :40002) │
│                          │    HTTP POST     │         ↓                │
│  detect 429/bot-block ───┼──────────────────┼→ /rotate endpoint        │
│                          │                  │         ↓                │
│  wait for response       │                  │  mutex + cooldown check  │
│         ↓                │                  │         ↓                │
│  retry original request  │    200 OK        │  warp-cli disconnect     │
│         ↓                │←─────────────────┼  warp-cli connect        │
│  return result           │                  │  wait for healthy        │
│                          │                  │  return new IP           │
└──────────────────────────┘                  └──────────────────────────┘
         ↕ SOCKS5                                       ↕
    socks5h://10.0.1.1:40001              warp-svc (127.0.0.1:40000)
         ↕                                              ↕
    socat relay (0.0.0.0:40001) ←───────── socat relay
```

## Part 1: Rotation service on the host

**File:** `/opt/subtrad/warp-rotate.py`

A minimal Python HTTP server (no dependencies, stdlib only):

- Listens on `0.0.0.0:40002`
- Single endpoint: `POST /rotate`
- On request:
  1. Acquire mutex (threading.Lock)
  2. Check cooldown: if last rotation < 30 seconds ago, return `{"status": "cooldown", "seconds_remaining": N}`
  3. Run `warp-cli --accept-tos disconnect`
  4. Wait 2 seconds
  5. Run `warp-cli --accept-tos connect`
  6. Wait up to 10 seconds for `warp-cli --accept-tos status` to return "Connected"
  7. Fetch new IP via `curl --socks5-hostname 127.0.0.1:40000 https://ifconfig.me`
  8. Update last_rotation timestamp
  9. Return `{"status": "rotated", "new_ip": "x.x.x.x", "elapsed_seconds": N}`
- On error: return `{"status": "error", "detail": "..."}`
- Health check: `GET /health` returns `{"status": "ok", "last_rotation": "ISO timestamp", "current_cooldown": N}`

**Key constraints:**
- Mutex ensures only one rotation at a time (even if 50 requests fail simultaneously)
- 30-second cooldown prevents rapid cycling
- Timeout on warp-cli connect (10s max)
- No external dependencies — only Python stdlib (http.server, subprocess, threading, json)

## Part 2: Systemd service

**File:** `/etc/systemd/system/warp-rotation.service`

```ini
[Unit]
Description=WARP IP Rotation HTTP Service
After=warp-svc.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/subtrad/warp-rotate.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Part 3: UFW firewall rule

```bash
# Allow only Docker coolify subnet to reach the rotation endpoint
ufw allow from 10.0.1.0/24 to any port 40002 comment "WARP rotation from SubTrad container"
```

Same pattern as the existing WARP relay rule on port 40001.

## Part 4: Backend integration

**File:** `backend/services/warp_rotator.py` (new)

```python
def rotate_warp_ip(rotation_url: str = "http://10.0.1.1:40002/rotate") -> dict | None:
    """Call host rotation service. Returns {"status": "rotated", "new_ip": ...} or None."""
```

**File:** `backend/services/subtitle_fetcher.py` (modify)

In `fetch_existing_subtitles()`:
- Catch yt-dlp DownloadError containing "Sign in to confirm" or "HTTP Error 429"
- Call `rotate_warp_ip()`
- If rotation succeeded, retry the download once
- If retry also fails, return None as before

**File:** `backend/services/youtube_api.py` (modify)

In `fetch_captions_via_transcript_lib()`:
- Catch `RequestBlocked` exception from youtube-transcript-api
- Call `rotate_warp_ip()`
- Retry once after rotation

**File:** `backend/services/audio_extractor.py` (modify)

In `extract_audio()`:
- Catch DownloadError containing "Sign in" or "429"
- Call `rotate_warp_ip()`
- Retry once

## Part 5: Config

**New env var in Coolify:**
- `SUBTRAD_WARP_ROTATION_URL` = `http://10.0.1.1:40002/rotate`

**In `backend/config.py`:**
- Add `warp_rotation_url: str = ""` to Settings

## Retry logic (all 3 files follow this pattern)

```
attempt 1: make request
  ↓ fails with 429/bot-block
rotate WARP IP (POST /rotate)
  ↓ success → new IP
attempt 2: retry same request
  ↓ fails again → give up, return None/raise
  ↓ succeeds → return result
```

Maximum 1 retry per request. No infinite loops.

## Part 6: Tests

**File:** `backend/tests/test_warp_rotator.py`
- Mock httpx.post to rotation endpoint
- Test successful rotation → returns new IP
- Test cooldown response → no retry
- Test rotation service unreachable → graceful failure (None)

**File:** Update existing tests
- `test_subtitle_fetcher.py`: test retry-after-rotation for yt-dlp 429
- `test_youtube_api.py`: test retry-after-rotation for RequestBlocked
- `test_audio_extractor.py`: test retry-after-rotation for DownloadError

## Execution order

| Step | What | Where | Depends on |
|------|------|-------|------------|
| 1 | Create warp-rotate.py | Host /opt/subtrad/ | Nothing |
| 2 | Create systemd service + UFW rule | Host | Step 1 |
| 3 | Test rotation endpoint from host | Host | Step 2 |
| 4 | Test rotation endpoint from container | Container | Step 3 |
| 5 | Create warp_rotator.py | Backend (agent) | Step 4 |
| 6 | Integrate retry logic in 3 service files | Backend (agent) | Step 5 |
| 7 | Tests | Backend (agent) | Step 6 |

**Steps 1-4 are infra (supervisor does it).** Steps 5-7 are coding (agent does it).

## Risk assessment

- **WARP rate limit:** Cloudflare may throttle frequent disconnect/connect cycles. 30s cooldown mitigates this.
- **Downtime during rotation:** ~5s window where SOCKS5 proxy is down. Requests in flight may fail. Acceptable — they'll be retried.
- **Same IP after rotation:** Cloudflare may reassign the same IP. No fix, but unlikely with their large pool.
- **warp-cli hangs:** 10s timeout prevents blocking forever.
