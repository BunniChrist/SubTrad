# Local Audio Batch Ingest Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a SubTrad endpoint and n8n workflow path so Bloc 1 can process batches of local MP3 files named after YouTube video IDs.

**Architecture:** Reuse the existing Whisper transcription pipeline by adding `POST /api/transcribe-local-file` in the backend. Then extend the existing Bloc 1 n8n workflow with a separate scheduled branch that lists local MP3 files, derives the YouTube URL from the filename, calls the new endpoint, and moves files to `processed/` or `error/`.

**Tech Stack:** FastAPI, Pydantic, pytest, sqlite-backed n8n workflow storage, Docker/Coolify runtime.

---

### Task 1: Backend endpoint

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/routers/translate.py`
- Test: `backend/tests/test_translate_endpoint.py`

**Step 1:** Add failing tests for `POST /api/transcribe-local-file`.

**Step 2:** Run `pytest backend/tests/test_translate_endpoint.py -q -k transcribe_local_file` and confirm failure.

**Step 3:** Add `TranscribeLocalFileRequest` and implement the endpoint using the existing Whisper response builder.

**Step 4:** Re-run the targeted tests until green.

### Task 2: Workflow branch

**Files:**
- Modify persisted n8n workflow `workflow_entity` and published `workflow_history` for workflow `6JKzvfiHIhsotxhw`
- Create runtime directories under `/root/contenuchretien/inbox-audio`

**Step 1:** Inspect current workflow graph and preserve the existing URL ingestion branch.

**Step 2:** Add a scheduled local-audio branch that lists `*.mp3`, extracts `video_id` from the filename, calls `/api/transcribe-local-file`, and feeds the same downstream formatting/review nodes.

**Step 3:** Add move commands for `processed/` and `error/`.

**Step 4:** Restart n8n and verify the workflow is loaded.

### Task 3: Verification

**Files:**
- Verify runtime via backend logs and n8n execution state

**Step 1:** Run the backend test suite relevant to translation/transcription.

**Step 2:** Trigger a controlled local-file execution and verify the MP3 is processed without SubTrad deleting the source file.

**Step 3:** Document any runtime caveat discovered during the first live run.
