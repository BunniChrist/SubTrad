# Agent Prompt — Phase 7: Cache System

## Setup

- **Branch:** `feature/cache-system`
- **Working directory:** `/root/Workspace/SubTrad`
- **First steps:**
  1. Read `agents.md` and follow it
  2. Read `superpowers/using-superpowers/SKILL.md` and announce your skill
  3. Create and switch to branch `feature/cache-system`
  4. Read `docs/subtrad-framing.md` for full product context

## Goal

Add a caching layer for translated subtitles. After 100 requests for the same video+language combination, cache the translated subtitles so subsequent requests are served instantly without re-processing.

## Context — What Already Exists

Phase 1-3 are merged on `main`:
- `backend/routers/translate.py` — POST /api/translate endpoint (full pipeline: fetch/transcribe → translate → return)
- `backend/config.py` — Settings with `cache_threshold: int = 100`
- `backend/models.py` — TranslateResponse with subtitles, platform, video_id, target_lang, etc.

The translate endpoint currently processes every request from scratch.

## Tech Stack

- SQLite (via `sqlite3` standard library) — no new dependencies
- Same pattern as other services

## New Files

```
backend/
  services/
    cache.py              — NEW: Subtitle cache (store/retrieve)
    request_counter.py    — NEW: Request counter per video+lang
  tests/
    test_cache.py         — NEW
    test_request_counter.py — NEW
```

## Tasks (TDD — test first, implement, commit)

### Task 1: Request counter

Create `backend/services/request_counter.py`:
- `class RequestCounter` initialized with SQLite db path
- Table: `request_counts(video_id TEXT, target_lang TEXT, count INTEGER, PRIMARY KEY(video_id, target_lang))`
- Methods:
  - `increment(video_id: str, target_lang: str) -> int` — increment and return new count
  - `get_count(video_id: str, target_lang: str) -> int` — return current count
  - `should_cache(video_id: str, target_lang: str) -> bool` — return True if count >= threshold

Tests (`backend/tests/test_request_counter.py`):
- Test increment from 0 → 1
- Test multiple increments → correct count
- Test should_cache False when under threshold
- Test should_cache True when at threshold (100)
- Test should_cache True when over threshold
- Test different video+lang combos are independent
- Use `:memory:` SQLite for tests

### Task 2: Subtitle cache

Create `backend/services/cache.py`:
- `class SubtitleCache` initialized with SQLite db path
- Table: `subtitle_cache(video_id TEXT, target_lang TEXT, subtitles_json TEXT, platform TEXT, duration_seconds INTEGER, detected_language TEXT, source TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(video_id, target_lang))`
- Methods:
  - `store(video_id: str, target_lang: str, response_data: dict) -> None` — store full response data as JSON
  - `retrieve(video_id: str, target_lang: str) -> dict | None` — return cached data or None
  - `exists(video_id: str, target_lang: str) -> bool` — check if cached

Tests (`backend/tests/test_cache.py`):
- Test store and retrieve returns correct data
- Test retrieve non-existent returns None
- Test exists True/False
- Test overwrite existing cache updates data
- Test subtitles JSON is correctly serialized/deserialized
- Use `:memory:` SQLite for tests

### Task 3: Wire cache into translate endpoint

Modify `backend/routers/translate.py`:

Insert cache logic at the **beginning** and **end** of the translate flow:

```python
# At the START of the endpoint:
cache = SubtitleCache("data/cache.db")
counter = RequestCounter("data/cache.db")

# 1. Check cache first
cached = cache.retrieve(video_id, target_lang)
if cached:
    return TranslateResponse(**cached, translation_status="cached")

# ... existing processing pipeline ...

# At the END (after successful translation):
# 2. Increment counter
count = counter.increment(video_id, target_lang)

# 3. Store in cache if threshold reached
if counter.should_cache(video_id, target_lang):
    cache.store(video_id, target_lang, response_data)
```

Add `"cached"` as a possible value for `translation_status` in the response.

Important: both SubtitleCache and RequestCounter should share the same SQLite database file (`data/cache.db`) to avoid multiple DB files.

### Task 4: Add cache config

Modify `backend/config.py`:
- Add `cache_db_path: str = "data/cache.db"` to Settings
- The translate endpoint should use `settings.cache_db_path` and `settings.cache_threshold`

Ensure `data/` directory is in `.gitignore` (it may already be from Phase 6).
Create `data/.gitkeep` if it doesn't exist.

### Task 5: Endpoint tests with cache

Add tests to `backend/tests/test_translate_endpoint.py` (or create new test file):
- Test first request: not cached, processes normally
- Test cached response returns immediately with `translation_status: "cached"`
- Test counter increments on each request
- Test cache is populated after threshold reached
- Mock the cache/counter services for unit tests

### Task 6: Verification

- [ ] All tests pass: `cd backend && python -m pytest tests/ -v -m "not integration"`
- [ ] Server starts at `http://localhost:8010/`
- [ ] First request for a video processes normally
- [ ] Request counter increments (verify via logs or debug)
- [ ] After threshold, subsequent requests return cached result (faster response)
- [ ] Cached response has `translation_status: "cached"`
- [ ] All code committed on `feature/cache-system`
- [ ] No TODO/FIXME left
- [ ] Clean `git status`
