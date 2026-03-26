# Agent Prompt — Phase 1: Backend API Core

## Setup

- **Branch:** `feature/backend-api-core`
- **Working directory:** `/root/Workspace`
- **First steps:**
  1. Read `agents.md` and follow it
  2. Read `superpowers/using-superpowers/SKILL.md` and announce your skill
  3. Create and switch to branch `feature/backend-api-core`
  4. Read `docs/subtranslate-framing.md` for full product context

## Goal

Build the FastAPI backend foundation for SubTranslate: URL validation, platform detection, video ID extraction, duration checking, subtitle fetching, and the main translate endpoint (stub orchestrator).

## Tech Stack

- Python 3.11+
- FastAPI + uvicorn
- yt-dlp (for metadata + subtitle extraction)
- pydantic / pydantic-settings
- pytest + httpx (for testing)

## Directory Structure

```
backend/
  main.py
  config.py
  models.py
  requirements.txt
  routers/
    __init__.py
    translate.py
  services/
    __init__.py
    url_validator.py
    video_id.py
    duration_checker.py
    subtitle_fetcher.py
  tests/
    __init__.py
    test_main.py
    test_url_validator.py
    test_video_id.py
    test_duration_checker.py
    test_subtitle_fetcher.py
    test_translate_endpoint.py
```

## Tasks (TDD — each task = test first, then implement, then commit)

### Task 1: Project scaffold + health endpoint

Create `backend/main.py` with a FastAPI app and a `GET /api/health` returning `{"status": "ok"}`. Add CORS middleware (allow all origins for dev). Create `backend/config.py` with settings:
- `max_duration_seconds: int = 720` (12 minutes)
- `cache_threshold: int = 100`
- `supported_languages: list[str] = ["fr", "es", "en", "ja"]`

Create `backend/requirements.txt` with all dependencies.

Test: `GET /api/health` returns 200 + `{"status": "ok"}`

### Task 2: URL validation + platform detection

Create `backend/services/url_validator.py` with:
- `validate_url(url: str) -> bool` — returns True if URL matches YouTube, Instagram, or TikTok
- `detect_platform(url: str) -> str | None` — returns "youtube", "instagram", "tiktok", or None

Supported URL formats:
- YouTube: `youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/`
- TikTok: `tiktok.com/@user/video/`, `vm.tiktok.com/`
- Instagram: `instagram.com/reel/`, `instagram.com/p/`

Tests: valid URLs for each platform, invalid URLs, empty string, edge cases.

### Task 3: Video ID extraction

Create `backend/services/video_id.py` with:
- `extract_video_id(url: str, platform: str) -> str` — extracts the video identifier

Examples:
- `youtube.com/watch?v=dQw4w9WgXcQ` → `dQw4w9WgXcQ`
- `youtu.be/dQw4w9WgXcQ` → `dQw4w9WgXcQ`
- `tiktok.com/@user/video/7123456789` → `7123456789`
- `instagram.com/reel/CxYz123Ab/` → `CxYz123Ab`

Tests: each platform format, short URLs, URLs with extra parameters.

### Task 4: Duration checker

Create `backend/services/duration_checker.py` with:
- A `DurationResult` dataclass: `allowed: bool`, `duration_seconds: int`, `redirect: str | None`
- `check_duration(duration_seconds: int) -> DurationResult`
  - If <= 720s: `allowed=True, redirect=None`
  - If > 720s: `allowed=False, redirect="premium"`

Tests: under limit, over limit, exactly at limit (720s should be allowed).

### Task 5: YouTube subtitle fetcher

Create `backend/services/subtitle_fetcher.py` with:
- `fetch_existing_subtitles(url: str) -> list[dict] | None` — uses yt-dlp to get existing captions
- `parse_srt(srt_content: str) -> list[dict]` — parses SRT format to `[{start, end, text}]`

Returns `None` if no subtitles available (this triggers Whisper fallback in Phase 2).

Tests: SRT parsing with sample content, empty input, multi-line subtitle entries.

### Task 6: POST /api/translate endpoint (stub orchestrator)

Create `backend/models.py`:
```python
class TranslateRequest(BaseModel):
    url: str
    target_lang: str  # "fr", "es", "en", "ja"

class TranslateResponse(BaseModel):
    platform: str
    video_id: str
    subtitles: list[dict]  # [{start, end, text}]
    duration_seconds: int
```

Create `backend/routers/translate.py`:
- `POST /api/translate` — validates URL, validates language, detects platform, extracts video ID, checks duration (redirect if >12 min), fetches existing subtitles
- For now, return subtitles untranslated (translation comes in Phase 3)
- If no subtitles found, return empty list with a flag `needs_transcription: true`

Register router in `backend/main.py`.

Tests:
- Invalid URL → 400
- Unsupported language → 400
- Valid YouTube URL → 200 with platform, video_id, subtitles (or needs_transcription flag)

## Verification Checklist

Before declaring done:
- [ ] All tests pass: `python -m pytest backend/tests/ -v`
- [ ] Server starts: `cd backend && uvicorn main:app --reload` works
- [ ] Health check: `curl http://localhost:8000/api/health` returns OK
- [ ] Translate endpoint responds to a real YouTube URL
- [ ] All code committed on `feature/backend-api-core`
- [ ] No TODO/FIXME left
- [ ] Clean `git status`
