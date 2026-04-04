# Instagram & TikTok Stabilization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stabilize Instagram and TikTok audio extraction, add clear 422 errors, retry blocked yt-dlp access once with WARP rotation, and expose transcript exports in VTT/TXT/Markdown formats.

**Architecture:** Keep `backend/routers/translate.py` as the single orchestrator for the shared yt-dlp flow. Add a small export utility module and narrow helpers for retry/error mapping so the YouTube path remains untouched.

**Tech Stack:** FastAPI, Pydantic, pytest, yt-dlp, faster-whisper integration, existing WARP rotator helper.

---

### Task 1: Add export format tests

**Files:**
- Create: `backend/tests/test_export_formats.py`
- Create: `backend/export_formats.py`

**Step 1: Write the failing test**

```python
def test_to_vtt_renders_webvtt_segments():
    assert to_vtt([{"start": 0.0, "end": 1.5, "text": "Hello"}]).startswith("WEBVTT")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_export_formats.py -v`
Expected: FAIL because module or functions do not exist.

**Step 3: Write minimal implementation**

```python
def to_vtt(segments):
    return "WEBVTT\n\n..."
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_export_formats.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests/test_export_formats.py backend/export_formats.py
git commit -m "feat: add transcript export formats"
```

### Task 2: Cover Instagram/TikTok endpoint behaviors with red tests

**Files:**
- Create: `backend/tests/test_instagram_tiktok.py`
- Modify: `backend/models.py`
- Modify: `backend/routers/translate.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("url, platform", [...])
def test_instagram_tiktok_whisper_flow_returns_exports(...):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_instagram_tiktok.py -v`
Expected: FAIL because `exports` and new error handling are missing.

**Step 3: Write minimal implementation**

```python
class ExportPayload(BaseModel):
    vtt: str
    txt: str
    md: str
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_instagram_tiktok.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests/test_instagram_tiktok.py backend/models.py backend/routers/translate.py
git commit -m "feat: stabilize instagram and tiktok translate flow"
```

### Task 3: Add yt-dlp retry logic and translation regression coverage

**Files:**
- Modify: `backend/routers/translate.py`
- Modify: `backend/tests/test_instagram_tiktok.py`

**Step 1: Write the failing tests**

```python
def test_blocked_duration_lookup_retries_after_warp_rotation(...):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_instagram_tiktok.py -v`
Expected: FAIL because retry/rotation path is missing.

**Step 3: Write minimal implementation**

```python
def _call_with_rotation_retry(operation):
    ...
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_instagram_tiktok.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/routers/translate.py backend/tests/test_instagram_tiktok.py
git commit -m "fix: retry blocked instagram tiktok ytdlp calls"
```

### Task 4: Full verification

**Files:**
- Modify: none expected

**Step 1: Run targeted tests**

Run: `python3 -m pytest backend/tests/test_export_formats.py backend/tests/test_instagram_tiktok.py -v`
Expected: PASS

**Step 2: Run full backend suite**

Run: `python3 -m pytest backend/tests/ -v`
Expected: PASS

**Step 3: Inspect git status**

Run: `git status --short`
Expected: clean worktree

**Step 4: Commit any remaining verified work**

```bash
git add docs/plans/2026-04-04-instagram-tiktok-stabilization-design.md docs/plans/2026-04-04-instagram-tiktok-stabilization.md
git commit -m "docs: add instagram tiktok stabilization plan"
```
