# LLM Translation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add LLM-powered subtitle translation to `/api/translate`, including prompt formatting, language detection, translation status metadata, and graceful fallback behavior.

**Architecture:** A new translation prompt module formats numbered subtitle batches for the OpenAI chat API and maps responses back onto original timestamps. A new translator service handles source-language detection, batch translation, and fallback behavior, while the existing translate router orchestrates captions vs. transcription vs. translation and exposes the resulting metadata in the API response.

**Tech Stack:** Python 3.12, FastAPI, OpenAI Python SDK, pytest

---

### Task 1: Translation prompt helpers

**Files:**
- Create: `backend/services/translation_prompts.py`
- Create: `backend/tests/test_translation_prompts.py`

**Steps:**
1. Write failing tests for prompt language naming, numbered segment formatting, response parsing, mismatch fallback, and empty segments.
2. Run `python -m pytest backend/tests/test_translation_prompts.py -v` and confirm failure.
3. Implement `get_translation_prompt` and `parse_translation_response`.
4. Re-run `python -m pytest backend/tests/test_translation_prompts.py -v` and confirm pass.
5. Commit with `feat: add translation prompt helpers`.

### Task 2: Translator service

**Files:**
- Create: `backend/services/translator.py`
- Create: `backend/tests/test_translator.py`

**Steps:**
1. Write failing tests for successful translation, empty input, same-language skip, batching, API error fallback, and source-language detection.
2. Run `python -m pytest backend/tests/test_translator.py -v -m "not integration"` and confirm failure.
3. Implement `detect_source_language` and `translate_subtitles` with 20-segment batching and OpenAI fallback handling.
4. Re-run `python -m pytest backend/tests/test_translator.py -v -m "not integration"` and confirm pass.
5. Add the real integration test for a short English-to-French batch.
6. Commit with `feat: add subtitle translator service`.

### Task 3: Endpoint and model wiring

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/routers/translate.py`
- Modify: `backend/services/transcriber.py`
- Modify: `backend/tests/test_translate_endpoint.py`

**Steps:**
1. Write failing endpoint tests for translated subtitle responses, skipped translation when source equals target, and translation fallback metadata.
2. Run `python -m pytest backend/tests/test_translate_endpoint.py -v` and confirm failure.
3. Extend response models with `target_lang`, `detected_language`, and `translation_status`.
4. Pass through Whisper detected language when available, otherwise rely on translator detection.
5. Wire translation orchestration into the router with graceful fallback.
6. Re-run `python -m pytest backend/tests/test_translate_endpoint.py -v` and confirm pass.
7. Commit with `feat: wire llm translation into endpoint`.

### Task 4: Full verification

**Files:**
- Verify: `backend/tests/`

**Steps:**
1. Run `python -m pytest backend/tests/ -v -m "not integration"`.
2. Run `python -m pytest backend/tests/ -v -m integration` with `SUBTRAD_OPENAI_API_KEY`.
3. Start `uvicorn main:app --host 0.0.0.0 --port 8010` from `backend/`.
4. POST `/api/translate` with `target_lang="fr"` and confirm translated subtitles plus `target_lang`, `detected_language`, and `translation_status`.
5. Check `rg -n "TODO|FIXME" backend docs`.
6. Confirm clean `git status`.
