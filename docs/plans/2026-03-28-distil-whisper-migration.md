# Distil-Whisper Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace OpenAI Whisper API transcription with local `faster-whisper` CPU inference while keeping the API response format unchanged.

**Architecture:** `backend/services/transcriber.py` will own a lazy singleton `WhisperModel` configured from settings and reused across requests. Routers will stop passing an API key for transcription, while translation continues using `openai`.

**Tech Stack:** Python, FastAPI, pytest, `faster-whisper`, `openai`

---

### Task 1: Update transcriber tests for the new API

**Files:**
- Modify: `backend/tests/test_transcriber.py`

**Step 1: Write the failing test**

Add tests that call `transcribe_audio()` and `transcribe_audio_with_metadata()` without `api_key`, verify singleton reuse, verify empty and missing files return empty payloads, and verify invalid files still raise `ValueError`.

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_transcriber.py -v`
Expected: FAIL because the production signature and implementation still require `api_key` and still depend on OpenAI Whisper.

**Step 3: Write minimal implementation**

Update `backend/services/transcriber.py` to use local `faster-whisper` with a singleton and preserve the existing payload shape.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_transcriber.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests/test_transcriber.py backend/services/transcriber.py backend/config.py backend/requirements.txt
git commit -m "feat: migrate transcription to distil whisper"
```

### Task 2: Update router call sites

**Files:**
- Modify: `backend/routers/translate.py`
- Modify: `backend/tests/test_translate_youtube_whisper.py`

**Step 1: Write the failing test**

Update route tests so mocked `transcribe_audio_with_metadata()` accepts only `audio_path`.

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_translate_youtube_whisper.py -v`
Expected: FAIL because the router still passes `settings.openai_api_key`.

**Step 3: Write minimal implementation**

Remove the obsolete transcription API key argument from every call site.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_translate_youtube_whisper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/routers/translate.py backend/tests/test_translate_youtube_whisper.py
git commit -m "fix: remove whisper api key call sites"
```

### Task 3: Full verification

**Files:**
- Verify: `backend/tests/`

**Step 1: Run focused backend verification**

Run: `cd backend && python -m pytest tests/ -v`
Expected: PASS

**Step 2: Review requirements**

Verify `backend/services/transcriber.py` no longer references OpenAI Whisper and `openai` remains only where translation uses it.

**Step 3: Check git status**

Run: `git status --short`
Expected: Only intended files changed.
