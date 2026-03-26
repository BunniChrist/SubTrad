# Whisper Transcription Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add audio extraction and Whisper API transcription as the subtitle fallback path for `/api/translate`.

**Architecture:** The fallback remains inside the existing FastAPI request flow. A new audio extractor service wraps `yt-dlp`, a transcriber service wraps the OpenAI Whisper API, and the translate router orchestrates existing captions vs. fallback transcription while guaranteeing temporary-file cleanup and explicit source metadata.

**Tech Stack:** Python 3.12, FastAPI, yt-dlp, OpenAI Python SDK, pytest

---

### Task 1: Repository and dependency setup

**Files:**
- Modify: `/.gitignore`
- Modify: `backend/requirements.txt`
- Modify: `backend/config.py`

**Steps:**
1. Add `.worktrees/` to `.gitignore` and allow tracked fixture audio under `backend/tests/fixtures/`.
2. Add `openai` to `backend/requirements.txt`.
3. Add `openai_api_key` to settings.
4. Create a local `.venv` and install backend dependencies.

### Task 2: Audio extraction service

**Files:**
- Create: `backend/services/audio_extractor.py`
- Create: `backend/tests/test_audio_extractor.py`

**Steps:**
1. Write failing unit tests for extraction path generation and cleanup behavior.
2. Run the targeted tests and confirm failure.
3. Implement `extract_audio` and `cleanup_audio`.
4. Re-run the targeted tests and confirm pass.

### Task 3: Whisper transcription service

**Files:**
- Create: `backend/services/transcriber.py`
- Create: `backend/tests/test_transcriber.py`

**Steps:**
1. Write failing unit tests for segment parsing, float timestamps, and empty audio handling.
2. Run the targeted tests and confirm failure.
3. Implement `transcribe_audio`.
4. Re-run the targeted tests and confirm pass.

### Task 4: Fixture audio

**Files:**
- Create: `backend/tests/fixtures/test_audio.mp3`

**Steps:**
1. Generate a tiny deterministic audio fixture.
2. Ensure `.gitignore` still allows this tracked file.

### Task 5: Translate endpoint fallback wiring

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/routers/translate.py`
- Modify: `backend/tests/test_translate_endpoint.py`

**Steps:**
1. Write failing endpoint tests for fallback transcription success and transcription failure.
2. Run the targeted endpoint tests and confirm failure.
3. Implement fallback orchestration, source metadata, and cleanup/error handling.
4. Re-run the targeted endpoint tests and confirm pass.

### Task 6: Integration verification

**Files:**
- Verify: `backend/tests/test_audio_extractor.py`
- Verify: `backend/tests/test_transcriber.py`

**Steps:**
1. Run the non-integration test suite.
2. Run the integration tests with `SUBTRAD_OPENAI_API_KEY`.
3. Start uvicorn on port `8010` and hit `/api/health`.
4. POST a real subtitle-missing YouTube URL to `/api/translate` and confirm fallback transcription.
5. Commit the branch work if status is clean except for unrelated changes.
